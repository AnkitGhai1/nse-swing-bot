"""
Market-hours scanner. Run every ~15 minutes between 9:30am and 3:15pm IST.

    python3 intraday.py            # does nothing outside market hours
    python3 intraday.py --force    # run anyway (for testing)

Each run:
  1. EXIT WATCH: checks your open positions against today's live price range
     and alarms you the moment a stop-loss or target is hit.
  2. BREAKOUT SCAN (if you have a free slot): looks for stocks that were
     already set up as of yesterday's close (uptrend, healthy RSI, MACD
     bullish) and are breaking out ABOVE their 20-day high right now, on
     above-normal volume for this time of day. Alerts + alarm, and logs the
     pick (source=intraday) so its accuracy is tracked separately from the
     end-of-day picks.

Honest notes:
  * This breakout rule is NOT covered by backtest.py -- Yahoo only offers
    ~60 days of 15-minute history, not enough to test it. Its LIVE accuracy is
    tracked in signals.csv (source=intraday) and in the daily summary; judge
    it on that after a couple of months. Turn it off with
    "intraday_enabled": false in config.json (or the INTRADAY_ENABLED var).
  * Yahoo's intraday NSE prices can lag the exchange by a few minutes, and
    GitHub's scheduler can start runs late. This is a heads-up system, not a
    tick-by-tick one: always check the live price in your broker app first.
"""

import argparse
import os
from datetime import time as dtime

from data import download, index_history
from rules import add_indicators, load_params, trade_levels
from screener import Candidate, size_position
from settings import load_config
from tracker import (load_signals, save_signals, open_tickers, open_sectors, blocked_tickers,
                     append_new_signals, update_open_positions, now_ist, today_ist)
from notify import notify, buy_texts, exit_texts, stop_raised_texts, flush_alarms
from universe import NIFTY_UNIVERSE, sector_of

OPEN_T, CLOSE_T = dtime(9, 15), dtime(15, 30)
SCAN_FROM, SCAN_UNTIL = dtime(9, 30), dtime(15, 15)
SESSION_MIN = 375
MAX_CHASE = 1.03   # skip if already >3% above the breakout level


def market_open_now() -> bool:
    n = now_ist()
    return n.weekday() < 5 and OPEN_T <= n.time() <= CLOSE_T


def session_fraction() -> float:
    n = now_ist()
    mins = (n.hour * 60 + n.minute) - (9 * 60 + 15)
    return min(max(mins / SESSION_MIN, 0.0), 1.0)


def scan(p: dict, exclude: set, exclude_sectors: set = None, force: bool = False):
    today = today_ist()
    exclude_sectors = exclude_sectors or set()
    prices = download(NIFTY_UNIVERSE, period="9mo", interval="1d")
    index_df = index_history(period="9mo")
    frac = max(session_fraction(), 0.15)   # volume is front-loaded; don't demand too little early
    out = []
    for t, df in prices.items():
        bare = t.replace(".NS", "")
        sec = sector_of(bare)
        if bare in exclude or sec in exclude_sectors or len(df) < 62:
            continue
        if df.index[-1].date() != today and not force:
            continue                        # no live bar for today yet
        ind = add_indicators(df, index_df=index_df, rs_lookback=p["rs_lookback"])
        y, live = ind.iloc[-2], ind.iloc[-1]    # yesterday (complete), today (in progress)
        # stock setup comes from yesterday's COMPLETED candle (today's is half-formed),
        # but the market-regime check uses TODAY's live index level -- if the market
        # has turned down this morning, stand aside straight away.
        setup = (y["Close"] > y["SMA50"] and y["SMA20"] > y["SMA50"]
                 and p["rsi_low"] <= y["RSI14"] <= p["rsi_high"]
                 and y["MACD"] > y["MACDsig"]
                 and (not p.get("regime_filter") or bool(live.get("REGIME_OK", True)))
                 and (not p.get("rs_filter") or bool(y.get("RS_OK", True))))
        if not setup:
            continue
        level = float(y["HIGH20"])
        price = float(live["Close"])
        if not (level < price <= level * MAX_CHASE):
            continue
        vol_pace = float(live["Volume"]) / (float(y["VOL20"]) * frac)
        if vol_pace < p["vol_mult"]:
            continue
        entry = round(price, 2)
        stop, target = trade_levels(entry, float(y["ATR14"]), p)
        if stop <= 0 or entry <= stop:
            continue
        out.append(Candidate(
            ticker=bare, score=min(100, int(60 + 10 * vol_pace)), close=entry,
            entry_price=entry, stop_loss=stop, target=target,
            reward_risk=round((target - entry) / (entry - stop), 2), qty=0,
            capital_used=0.0, rsi=round(float(y["RSI14"]), 1),
            reasons=(f"broke 20-day high ₹{level:.2f}; volume running {vol_pace:.1f}x normal "
                     f"for this time of day; daily uptrend + MACD bullish"),
            source="intraday", atr_entry=round(float(y["ATR14"]), 2), sector=sec,
        ))
    out.sort(key=lambda c: c.score, reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not args.force and not market_open_now():
        print(f"[intraday] market closed at {now_ist():%a %H:%M} IST -- nothing to do.")
        return

    cfg = load_config()
    p = load_params()
    rows = load_signals()

    # 1) exit watch -- expiry is handled by the end-of-day run
    rows, events = update_open_positions(rows, params=p, allow_expiry=False)
    for ev, row in events:
        notify(ev, *(stop_raised_texts(row) if ev == "STOP_RAISED" else exit_texts(ev, row)))

    # 2) breakout scan
    enabled = str(os.environ.get("INTRADAY_ENABLED", cfg.get("intraday_enabled", True))).lower() != "false"
    t = now_ist().time()
    in_window = args.force or (SCAN_FROM <= t <= SCAN_UNTIL)
    today = today_ist().isoformat()
    held = open_tickers(rows)
    intraday_today = sum(1 for r in rows if r["date_suggested"] == today and r.get("source") == "intraday")
    slots = cfg["max_open_positions"] - len(held)
    budget = min(slots, cfg["max_new_signals_per_run"] - intraday_today)

    from main import edge_ok
    if enabled and in_window and budget > 0 and edge_ok(cfg):
        cands = scan(p, blocked_tickers(rows, events), open_sectors(rows), force=args.force)
        sized = [size_position(c, cfg["capital"], cfg["risk_pct_per_trade"], cfg["max_open_positions"])
                 for c in cands]
        picks = [c for c in sized if c.qty > 0][:budget]
        for c in picks:
            notify("INTRADAY_BUY", *buy_texts(c))
        rows = append_new_signals(rows, picks)
        print(f"[intraday] {len(picks)} new breakout alert(s).")
    else:
        print(f"[intraday] scan skipped (enabled={enabled}, window={in_window}, budget={budget}).")

    flush_alarms()
    save_signals(rows)


if __name__ == "__main__":
    main()
