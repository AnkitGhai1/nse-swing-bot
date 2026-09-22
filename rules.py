"""
The trading rules, in one place, shared by the live screener AND the
backtester -- so what gets backtested is exactly what sends you alerts.

All indicators are "causal": the value on day t only uses prices up to and
including day t. That's what keeps the backtest free of look-ahead bias.

THE RULES
  Entry (all must be true on the latest completed daily candle):
    - Market regime OK      : NIFTY 50 itself is in an uptrend. Swing longs
                              fail far more often when the whole market is
                              falling, so the bot stands aside. [regime_filter]
    - Relative strength OK  : the stock beat the NIFTY over the last ~3
                              months. Buy leaders, not laggards. [rs_filter]
    - Score >= min_score    : 0-100 from trend, RSI, MACD, volume, breakout
                              proximity (weights below).
  Exit, whichever comes first:
    - stop-loss   = entry - stop_atr x ATR(14)
    - trailing stop (if trail_atr > 0): once the stock rises, the stop
      follows it up at trail_atr x ATR below the highest close so far, and
      never moves down. Locks in profit if a winner turns around.
    - target      = entry + target_atr x ATR(14)
    - time        = max_hold_days (~1 month)

Parameters live in DEFAULT_PARAMS. The weekly optimiser (backtest.py) may
write params.json with tuned values -- but only ones that passed its
out-of-sample checks. load_params() picks those up automatically.
"""

import json
import os

import numpy as np
import pandas as pd

from indicators import sma, rsi, macd, atr

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params.json")

DEFAULT_PARAMS = {
    "min_score": 60,        # minimum 0-100 score to flag a BUY
    "rsi_low": 45,          # RSI "healthy zone" lower bound
    "rsi_high": 65,         # RSI "healthy zone" upper bound (avoid overbought)
    "vol_mult": 1.2,        # today's volume must exceed this x 20-day avg
    "near_high_pct": 0.97,  # close within 3% of 20-day high = breakout zone
    "stop_atr": 1.5,        # initial stop = entry - stop_atr x ATR(14)
    "target_atr": 3.0,      # target      = entry + target_atr x ATR(14)
    "trail_atr": 0.0,       # trailing stop distance in ATRs (0 = off by default;
                            # the weekly backtest turns it on only if it proves better)
    "max_hold_days": 22,    # ~1 month; exit at the close if nothing else hit
    "regime_filter": 1,     # 1 = only buy when NIFTY 50 is in an uptrend
    "rs_filter": 1,         # 1 = only buy stocks outperforming NIFTY
    "rs_lookback": 63,      # ~3 months, for the relative-strength comparison
}

# Score weights -- add up to exactly 100
W_TREND, W_RSI_ZONE, W_RSI_RISING, W_MACD, W_VOLUME, W_NEAR_HIGH = 25, 20, 10, 15, 15, 15


def load_params() -> dict:
    p = dict(DEFAULT_PARAMS)
    if os.path.exists(PARAMS_PATH):
        try:
            with open(PARAMS_PATH) as f:
                tuned = json.load(f)
            p.update({k: v for k, v in tuned.get("params", {}).items() if k in p})
        except Exception as e:
            print(f"[warn] could not read params.json, using defaults: {e}")
    return p


def add_indicators(df: pd.DataFrame, index_df: pd.DataFrame = None,
                   rs_lookback: int = 63) -> pd.DataFrame:
    """df needs Open/High/Low/Close/Volume. index_df is NIFTY 50 history; if
    given, adds REGIME_OK (market healthy) and RS_OK (stock beating index)."""
    out = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    c = out["Close"]
    out["SMA20"] = sma(c, 20)
    out["SMA50"] = sma(c, 50)
    out["RSI14"] = rsi(c, 14)
    out["RSI14_3ago"] = out["RSI14"].shift(3)
    m, s, _ = macd(c)
    out["MACD"], out["MACDsig"] = m, s
    out["VOL20"] = out["Volume"].rolling(20).mean()
    out["HIGH20"] = c.rolling(20).max()
    out["ATR14"] = atr(out, 14)
    out["ready"] = np.arange(len(out)) >= 60

    if index_df is not None and not index_df.empty:
        ic = index_df["Close"].reindex(out.index, method="ffill")
        regime = (ic > sma(ic, 50)) & (sma(ic, 20) > sma(ic, 50))
        out["REGIME_OK"] = regime.fillna(False)
        stock_ret = c.pct_change(rs_lookback)
        index_ret = ic.pct_change(rs_lookback)
        out["RS_OK"] = (stock_ret > index_ret).fillna(False)
    else:
        out["REGIME_OK"] = True
        out["RS_OK"] = True
    return out


def score_frame(ind: pd.DataFrame, p: dict) -> pd.Series:
    """Vectorised 0-100 score for every row (used by the backtester).
    Rows failing the regime / relative-strength filters score 0."""
    trend = (ind["Close"] > ind["SMA50"]) & (ind["SMA20"] > ind["SMA50"])
    rsi_zone = ind["RSI14"].between(p["rsi_low"], p["rsi_high"])
    rsi_rising = rsi_zone & (ind["RSI14"] > ind["RSI14_3ago"])
    macd_bull = ind["MACD"] > ind["MACDsig"]
    vol_surge = ind["Volume"] > p["vol_mult"] * ind["VOL20"]
    near_high = ind["Close"] >= p["near_high_pct"] * ind["HIGH20"]
    score = (
        W_TREND * trend + W_RSI_ZONE * rsi_zone + W_RSI_RISING * rsi_rising
        + W_MACD * macd_bull + W_VOLUME * vol_surge + W_NEAR_HIGH * near_high
    ).astype(int)
    score[~ind["ready"]] = 0
    if p.get("regime_filter"):
        score[~ind["REGIME_OK"].astype(bool)] = 0
    if p.get("rs_filter"):
        score[~ind["RS_OK"].astype(bool)] = 0
    return score


def reasons_for_row(row: pd.Series, p: dict) -> str:
    r = []
    if row["Close"] > row["SMA50"] and row["SMA20"] > row["SMA50"]:
        r.append("uptrend (price>SMA50, SMA20>SMA50)")
    if p["rsi_low"] <= row["RSI14"] <= p["rsi_high"]:
        r.append(f"RSI {row['RSI14']:.0f} in healthy zone")
        if row["RSI14"] > row["RSI14_3ago"]:
            r.append("RSI rising")
    if row["MACD"] > row["MACDsig"]:
        r.append("MACD bullish")
    if row["Volume"] > p["vol_mult"] * row["VOL20"]:
        r.append(f"volume {row['Volume'] / row['VOL20']:.1f}x 20d avg")
    if row["Close"] >= p["near_high_pct"] * row["HIGH20"]:
        r.append("near 20-day high (breakout zone)")
    if p.get("rs_filter") and row.get("RS_OK", False):
        r.append("outperforming NIFTY")
    if p.get("regime_filter") and row.get("REGIME_OK", False):
        r.append("NIFTY itself in uptrend")
    return "; ".join(r)


def trade_levels(entry: float, atr_val: float, p: dict):
    stop = round(entry - p["stop_atr"] * atr_val, 2)
    target = round(entry + p["target_atr"] * atr_val, 2)
    return stop, target


def trailing_stop(initial_stop: float, highest_close: float, atr_at_entry: float,
                  p: dict) -> float:
    """Stop only ever moves UP: the higher of the initial stop and
    (highest close so far - trail_atr x ATR at entry)."""
    trail = float(p.get("trail_atr", 0) or 0)
    if trail <= 0 or atr_at_entry <= 0:
        return initial_stop
    return round(max(initial_stop, highest_close - trail * atr_at_entry), 2)
