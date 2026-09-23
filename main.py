"""
End-of-day run. Runs automatically at ~4:20pm IST on trading days (or run
it yourself any time after 3:30pm IST):

    python3 main.py

  1. Checks every OPEN position against today's full daily candle; closes
     any that hit target / stop-loss / the 1-month limit, with alerts.
  2. Screens the stock universe on today's COMPLETED daily candles for fresh
     BUY setups for tomorrow (skipping stocks you already hold).
  3. Sends a running live-accuracy summary.
  4. Saves everything to signals.csv.
"""

import json

from notify import (notify, buy_texts, exit_texts, stop_raised_texts, send_message,
                    format_summary, flush_alarms)
from rules import load_params, PARAMS_PATH
from screener import run_screener
from settings import load_config
from tracker import (load_signals, save_signals, open_tickers, open_sectors, blocked_tickers,
                     append_new_signals, update_open_positions, accuracy_stats)
from universe import NIFTY_UNIVERSE


def edge_ok(cfg: dict) -> bool:
    """False only if the last weekly backtest found no edge AND the pause is on."""
    if not cfg.get("pause_when_no_edge", True):
        return True
    try:
        with open(PARAMS_PATH) as f:
            return bool(json.load(f).get("edge_ok", True))
    except Exception:
        return True


def main():
    cfg = load_config()
    p = load_params()
    rows = load_signals()

    # 1) update open positions
    rows, events = update_open_positions(rows, params=p, allow_expiry=True)
    for ev, row in events:
        notify(ev, *(stop_raised_texts(row) if ev == "STOP_RAISED" else exit_texts(ev, row)))

    # 2) new candidates
    held = open_tickers(rows)
    slots_free = max(cfg["max_open_positions"] - len(held), 0)
    max_new = min(cfg["max_new_signals_per_run"], slots_free)
    note = ""
    new = []
    if not edge_ok(cfg):
        note = "⏸ New BUY alerts paused: the latest weekly backtest found no edge on unseen data."
    elif max_new > 0:
        new, note = run_screener(NIFTY_UNIVERSE, capital=cfg["capital"],
                                 risk_pct=cfg["risk_pct_per_trade"],
                                 max_open_positions=cfg["max_open_positions"],
                                 max_results=max_new,
                                 exclude_tickers=blocked_tickers(rows, events),
                                 exclude_sectors=open_sectors(rows), params=p)
        for c in new:
            notify("BUY", *buy_texts(c))
        rows = append_new_signals(rows, new)
    else:
        note = f"All {cfg['max_open_positions']} slots in use — no new picks until one closes."

    # 3) live accuracy, split by source
    s_all = accuracy_stats(rows)
    s_intra = accuracy_stats(rows, source="intraday")
    if s_intra.get("total_closed"):
        note += (f"\nIntraday alerts alone: {s_intra['wins']}/{s_intra['total_closed']} wins "
                 f"({s_intra['win_rate_pct']}%), P&L ₹{s_intra['total_pnl']}")
    send_message(format_summary(s_all, len(new), note.strip()))

    save_signals(rows)          # save the trade log first...
    print("[done] signals.csv updated.")
    flush_alarms()              # ...then ring (each alarm has a hard time limit)


if __name__ == "__main__":
    main()
