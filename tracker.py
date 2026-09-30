"""
Trade log + accuracy tracker.

signals.csv holds one row per suggested trade and is the single source of
truth for both "what's currently open" and "how good have the calls been".

status is one of: OPEN, TARGET_HIT, STOP_HIT, TRAIL_STOP, TREND_EXIT, EXPIRED
source is one of: daily (end-of-day screener), intraday (market-hours scanner),
                  crossover (20/50 moving-average trend track, kept separate)

update_open_positions() is called both by the end-of-day run and by every
intraday run, so a stop-loss or target hit at 11am is alerted at ~11am, not
after the close.
"""

import csv
import os
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Tuple

import pandas as pd

from data import download
from rules import trailing_stop
from universe import sector_of

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "signals.csv")
IST = timezone(timedelta(hours=5, minutes=30))
FIELDS = [
    "id", "date_suggested", "ticker", "sector", "source", "entry_price",
    "stop_initial", "stop_loss", "atr_entry", "target", "qty", "capital_used",
    "status", "exit_price", "exit_date", "pnl", "pnl_pct", "holding_days", "reasons",
]
CLOSED = ("TARGET_HIT", "STOP_HIT", "TRAIL_STOP", "TREND_EXIT", "EXPIRED")


def is_crossover(r: Dict) -> bool:
    return r.get("source") == "crossover"


def track_rows(rows: List[Dict], crossover: bool) -> List[Dict]:
    """The main rules (daily + intraday) and the crossover track are separate
    strategies with their own slots and their own track record."""
    return [r for r in rows if is_crossover(r) == crossover]


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def load_signals() -> List[Dict]:
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if not r.get("source"):
            r["source"] = "daily"
        if not r.get("stop_initial"):
            r["stop_initial"] = r.get("stop_loss", "")
        if not r.get("sector"):
            r["sector"] = sector_of(r.get("ticker", ""))
    return rows


def save_signals(rows: List[Dict]) -> None:
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def open_tickers(rows: List[Dict]) -> set:
    return {r["ticker"] for r in rows if r["status"] == "OPEN"}


def open_sectors(rows: List[Dict]) -> set:
    """Sectors already held -- the bot takes at most one position per sector."""
    return {r.get("sector") or sector_of(r["ticker"]) for r in rows if r["status"] == "OPEN"}


def blocked_tickers(rows: List[Dict], events=()) -> set:
    """Held now, suggested today, exited today, or closed during this run ->
    don't suggest again (avoids 'SELL X' followed seconds later by 'BUY X')."""
    today = today_ist().isoformat()
    blocked = {r["ticker"] for r in rows if r["status"] == "OPEN"
               or r.get("date_suggested") == today or r.get("exit_date") == today}
    return blocked | {row["ticker"] for _, row in events}


def append_new_signals(rows: List[Dict], candidates) -> List[Dict]:
    next_id = max((int(r["id"]) for r in rows), default=0) + 1
    today = today_ist().isoformat()
    for c in candidates:
        rows.append({
            "id": next_id, "date_suggested": today, "ticker": c.ticker,
            "sector": getattr(c, "sector", sector_of(c.ticker)),
            "source": getattr(c, "source", "daily"),
            "entry_price": c.entry_price, "stop_initial": c.stop_loss,
            "stop_loss": c.stop_loss, "atr_entry": getattr(c, "atr_entry", 0.0),
            "target": c.target if c.target else "", "qty": c.qty, "capital_used": c.capital_used,
            "status": "OPEN", "exit_price": "", "exit_date": "", "pnl": "",
            "pnl_pct": "", "holding_days": 0, "reasons": c.reasons,
        })
        next_id += 1
    return rows


def _close(row: Dict, status: str, exit_price: float, when: date) -> None:
    entry, qty = float(row["entry_price"]), int(float(row["qty"]))
    row["status"] = status
    row["exit_price"] = round(exit_price, 2)
    row["exit_date"] = when.isoformat()
    row["pnl"] = round((exit_price - entry) * qty, 2)
    row["pnl_pct"] = round((exit_price - entry) / entry * 100, 2)


def update_open_positions(rows: List[Dict], params: Dict = None,
                          allow_expiry: bool = True) -> Tuple[List[Dict], List]:
    """Checks every OPEN row against the daily bars since it was suggested
    (today's bar is the live, in-progress one during market hours), maintains
    the trailing stop, and closes anything that hit a level.
    Returns (rows, events); events are (status, row) for alerts."""
    from rules import DEFAULT_PARAMS
    from settings import load_config
    from indicators import sma
    p = params or DEFAULT_PARAMS
    xo = load_config()
    events = []
    open_rows = [r for r in rows if r["status"] == "OPEN"]
    if not open_rows:
        return rows, events

    prices = download(sorted({f"{r['ticker']}.NS" for r in open_rows}),
                      period="1y", interval="1d")
    today = today_ist()

    for row in open_rows:
        df = prices.get(f"{row['ticker']}.NS")
        if df is None or df.empty:
            continue
        crossover = is_crossover(row)
        rp = dict(p, trail_atr=0) if crossover else p          # crossover: fixed stop, no trailing
        max_hold_days = int(xo["crossover_max_hold_days"] if crossover else p.get("max_hold_days", 22))
        entry = float(row["entry_price"])
        target = float(row["target"] or 0) or float("inf")     # crossover has no fixed target
        stop0 = float(row.get("stop_initial") or row["stop_loss"])
        atr_e = float(row.get("atr_entry") or 0)
        prev_stop = float(row["stop_loss"])
        suggested = date.fromisoformat(row["date_suggested"])
        after = df[[d.date() > suggested for d in df.index]]
        row["holding_days"] = len(after)

        cur_stop, highest_close = stop0, None
        for idx, bar in after.iterrows():
            when = idx.date()
            # stop for today is based on closes up to YESTERDAY (never lowers)
            cur_stop = stop0 if highest_close is None else trailing_stop(stop0, highest_close, atr_e, rp)
            trailed = cur_stop > stop0 + 1e-9
            if bar["Open"] <= cur_stop:
                _close(row, "TRAIL_STOP" if trailed else "STOP_HIT", float(bar["Open"]), when); break
            if bar["Open"] >= target:
                _close(row, "TARGET_HIT", float(bar["Open"]), when); break
            if bar["Low"] <= cur_stop:      # stop assumed hit before target
                _close(row, "TRAIL_STOP" if trailed else "STOP_HIT", cur_stop, when); break
            if bar["High"] >= target:
                _close(row, "TARGET_HIT", target, when); break
            highest_close = float(bar["Close"]) if highest_close is None else max(highest_close, float(bar["Close"]))

        if row["status"] == "OPEN":
            new_stop = stop0 if highest_close is None else trailing_stop(stop0, highest_close, atr_e, rp)
            row["stop_loss"] = new_stop
            if new_stop > prev_stop + 0.01:
                events.append(("STOP_RAISED", dict(row, prev_stop=prev_stop)))
            if allow_expiry and crossover and len(after):
                # end-of-day only: trend over when the fast average closes below the slow one
                fast = sma(df["Close"], int(xo["crossover_fast"])).iloc[-1]
                slow = sma(df["Close"], int(xo["crossover_slow"])).iloc[-1]
                if fast < slow:
                    _close(row, "TREND_EXIT", float(after["Close"].iloc[-1]), today)
            if row["status"] == "OPEN" and allow_expiry and len(after) >= max_hold_days:
                _close(row, "EXPIRED", float(after["Close"].iloc[-1]), today)

        if row["status"] != "OPEN":
            events.append((row["status"], row))

    return rows, events


def accuracy_stats(rows: List[Dict], source: str = None) -> Dict:
    closed = [r for r in rows if r["status"] in CLOSED
              and (source is None or r.get("source", "daily") == source)]
    if not closed:
        return {"total_closed": 0}
    pnl = [float(r["pnl"] or 0) for r in closed]
    pct = [float(r["pnl_pct"] or 0) for r in closed]
    wins = [x for x in pct if x > 0]
    losses = [x for x in pct if x <= 0]
    gross_win = sum(p for p in pnl if p > 0)
    gross_loss = -sum(p for p in pnl if p <= 0)
    return {
        "total_closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(closed), 1),
        "total_pnl": round(sum(pnl), 2),
        "avg_win_pct": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss_pct": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
    }
