"""
End-of-day swing-trade screener for NSE stocks.

The rules themselves live in rules.py (shared with the backtester). This file
applies them to the latest completed daily candle, verifies the prices against
NSE's official close where possible, and sizes the position for your capital.

Position sizing:
    risk_amount    = capital x risk_pct_per_trade
    qty_by_risk    = risk_amount / (entry - stop_loss)
    qty_by_capital = (capital / max_open_positions) / entry
    qty            = floor(min(qty_by_risk, qty_by_capital))
"""

import math
from dataclasses import dataclass, asdict
from typing import List, Optional, Set

from data import download, index_history, verify_against_nse
from rules import add_indicators, score_frame, reasons_for_row, trade_levels, load_params
from universe import sector_of


@dataclass
class Candidate:
    ticker: str
    score: int
    close: float
    entry_price: float
    stop_loss: float
    target: float
    reward_risk: float
    qty: int
    capital_used: float
    rsi: float
    reasons: str
    source: str = "daily"
    atr_entry: float = 0.0
    sector: str = "Other"


def size_position(cand: Candidate, capital: float, risk_pct: float,
                  max_open_positions: int) -> Candidate:
    per_share_risk = cand.entry_price - cand.stop_loss
    qty_by_risk = (capital * risk_pct) / per_share_risk if per_share_risk > 0 else 0
    qty_by_capital = (capital / max_open_positions) / cand.entry_price
    cand.qty = max(int(math.floor(min(qty_by_risk, qty_by_capital))), 0)
    cand.capital_used = round(cand.qty * cand.entry_price, 2)
    return cand


def run_screener(universe: List[str], capital: float, risk_pct: float,
                 max_open_positions: int, max_results: int = 5,
                 exclude_tickers: Optional[Set[str]] = None,
                 exclude_sectors: Optional[Set[str]] = None,
                 params: Optional[dict] = None,
                 verify: bool = True):
    """Returns (candidates, data_quality_note)."""
    p = params or load_params()
    exclude_tickers = exclude_tickers or set()
    exclude_sectors = exclude_sectors or set()

    prices = download(universe, period="9mo", interval="1d")
    index_df = index_history(period="9mo")
    note = ""
    if index_df is None or index_df.empty:
        note = "⚠️ NIFTY index data unavailable — market-regime filter is off for this run."

    suspect = set()
    if verify:
        suspect, status = verify_against_nse(prices)
        if suspect:
            note += ("\n" if note else "") + status

    candidates = []
    for t, df in prices.items():
        bare = t.replace(".NS", "")
        sec = sector_of(bare)
        if bare in exclude_tickers or sec in exclude_sectors or t in suspect or len(df) < 61:
            continue
        ind = add_indicators(df, index_df=index_df, rs_lookback=p["rs_lookback"])
        score = int(score_frame(ind, p).iloc[-1])
        if score < p["min_score"]:
            continue
        last = ind.iloc[-1]
        entry = round(float(last["Close"]), 2)
        atr_val = float(last["ATR14"])
        stop, target = trade_levels(entry, atr_val, p)
        if stop <= 0 or entry <= stop:
            continue
        candidates.append(Candidate(
            ticker=bare, score=score, close=entry, entry_price=entry,
            stop_loss=stop, target=target,
            reward_risk=round((target - entry) / (entry - stop), 2),
            qty=0, capital_used=0.0, rsi=round(float(last["RSI14"]), 1),
            reasons=reasons_for_row(last, p), atr_entry=round(atr_val, 2), sector=sec,
        ))

    candidates.sort(key=lambda c: c.score, reverse=True)

    # one position per sector, best-scored first
    picked, used_sectors = [], set(exclude_sectors)
    for c in candidates:
        if c.sector in used_sectors:
            continue
        c = size_position(c, capital, risk_pct, max_open_positions)
        if c.qty <= 0:
            continue
        picked.append(c)
        used_sectors.add(c.sector)
        if len(picked) >= max_results:
            break
    return picked, note


if __name__ == "__main__":
    from universe import NIFTY_UNIVERSE
    picks, note = run_screener(NIFTY_UNIVERSE, capital=40000, risk_pct=0.02, max_open_positions=3)
    print(note)
    for r in picks:
        print(asdict(r))
