"""
End-of-day run. Runs automatically at ~4:20pm IST on trading days (or run
it yourself any time after 3:30pm IST):

    python3 main.py

  1. Checks every OPEN position against today's full daily candle; closes
     any that hit target / stop-loss / the 1-month limit, with alerts.
  2. Screens the stock universe on today's COMPLETED daily candles for fresh
     BUY setups for tomorrow (skipping stocks you already hold).
  3. Trend track: separately looks for fresh 20/50 moving-average crossovers
     (own slots, own track record, source=crossover).
  4. Sends a running live-accuracy summary for each strategy.
  5. Saves everything to signals.csv.
"""

import json

from notify import (notify, buy_texts, exit_texts, stop_raised_texts, send_message,
                    format_summary, flush_alarms)
from rules import load_params, PARAMS_PATH
from screener import run_screener, run_crossover
from settings import load_config
from tracker import (load_signals, save_signals, open_tickers, open_sectors, blocked_tickers,
                     append_new_signals, update_open_positions, accuracy_stats, track_rows)
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

    # 2) new candidates -- main rules (their own slots)
    main_rows = track_rows(rows, crossover=False)
    held = open_tickers(main_rows)
    slots_free = max(cfg["max_open_positions"] - len(held), 0)
    max_new = min(cfg["max_new_signals_per_run"], slots_free)
    note = ""
    new = []
    if not edge_ok(cfg):
        note = "⏸ Main-rules BUY alerts paused: the latest weekly backtest found no edge on unseen data."
    elif max_new > 0:
        new, note = run_screener(NIFTY_UNIVERSE, capital=cfg["capital"],
                                 risk_pct=cfg["risk_pct_per_trade"],
                                 max_open_positions=cfg["max_open_positions"],
                                 max_results=max_new,
                                 exclude_tickers=blocked_tickers(rows, events),
                                 exclude_sectors=open_sectors(main_rows), params=p)
        for c in new:
            notify("BUY", *buy_texts(c))
        rows = append_new_signals(rows, new)
    else:
        note = f"All {cfg['max_open_positions']} main-rules slots in use — no new picks until one closes."

    # 3) trend track: 20/50 crossover (separate slots and track record)
    new_x = []
    if cfg.get("crossover_enabled", True):
        x_rows = track_rows(rows, crossover=True)
        x_free = max(int(cfg["crossover_slots"]) - len(open_tickers(x_rows)), 0)
        x_max = min(cfg["max_new_signals_per_run"], x_free)
        if x_max > 0:
            new_x = run_crossover(NIFTY_UNIVERSE, capital=cfg["capital"],
                                  risk_pct=cfg["risk_pct_per_trade"],
                                  slots=int(cfg["crossover_slots"]), max_results=x_max,
                                  exclude_tickers=blocked_tickers(rows, events) | {c.ticker for c in new},
                                  exclude_sectors=open_sectors(x_rows),
                                  fast=int(cfg["crossover_fast"]), slow=int(cfg["crossover_slow"]),
                                  stop_atr=float(cfg["crossover_stop_atr"]))
            for c in new_x:
                notify("CROSSOVER_BUY", *buy_texts(c))
            rows = append_new_signals(rows, new_x)

    # 4) live accuracy, split by strategy
    main_rows = track_rows(rows, crossover=False)
    s_main = accuracy_stats(main_rows)
    s_intra = accuracy_stats(main_rows, source="intraday")
    if s_intra.get("total_closed"):
        note += (f"\nIntraday alerts alone: {s_intra['wins']}/{s_intra['total_closed']} wins "
                 f"({s_intra['win_rate_pct']}%), P&L ₹{s_intra['total_pnl']}")
    if cfg.get("crossover_enabled", True):
        x_rows = track_rows(rows, crossover=True)
        sx = accuracy_stats(x_rows)
        n_open = len(open_tickers(x_rows))
        line = f"\n📈 Trend track (20/50): {len(new_x)} new today, {n_open} open"
        if sx.get("total_closed"):
            line += (f", {sx['wins']}/{sx['total_closed']} closed trades won ({sx['win_rate_pct']}%), "
                     f"P&L ₹{sx['total_pnl']}")
        note += line
    if cfg.get("paper_mode", True):
        note += "\n📝 Paper mode: all alerts are practice until a strategy proves itself live."
    send_message(format_summary(s_main, len(new), note.strip()))

    save_signals(rows)          # save the trade log first...
    print("[done] signals.csv updated.")
    flush_alarms()              # ...then ring (each alarm has a hard time limit)


if __name__ == "__main__":
    main()
