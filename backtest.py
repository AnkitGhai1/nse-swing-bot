"""
Backtester + walk-forward self-tuning.

    python3 backtest.py                # full walk-forward test + tuning, writes params.json
    python3 backtest.py --no-optimize  # just backtest the current params over all history
    python3 backtest.py --years 8      # use more history (default 6)

HOW THE BACKTEST AVOIDS FOOLING YOU
  * No look-ahead: indicators on day t only use data up to day t. A signal
    on day t's close is entered at day t+1's OPEN (that's when you could
    actually buy after an evening alert) -- not at the close you already saw.
  * Realistic exits: gap through the stop/target at the open -> exit at the
    open price. If stop and target are both touched the same day, we assume
    the stop was hit first (worst case).
  * Costs: 0.30% round trip deducted from every trade (brokerage + STT +
    exchange + stamp + GST on delivery, approx).
  * One position per stock at a time; portfolio simulation respects your
    capital, slot count and risk-per-trade sizing, and compounds profits.

HOW THE SELF-TUNING AVOIDS OVER- AND UNDER-FITTING
  1. Tiny, coarse grid: 4 parameters x 3 values = 81 combos. Few knobs =
     little room to curve-fit noise. (Under-fitting guard: those knobs do
     cover the things that matter most -- entry strictness, RSI ceiling,
     stop width and target width.)
  2. Walk-forward: tune on 2 years, then test the chosen params on the NEXT
     6 months the tuner never saw. Slide forward 6 months, repeat. Only the
     stitched-together unseen ("out-of-sample") periods count as the
     honest score.
  3. Robust objective: not raw win-rate (easy to game with tiny targets and
     huge stops) and not raw profit per trade (ignores how long your money
     is stuck), but a PESSIMISTIC edge per day of capital used:
     (mean return - 1 standard error) / average holding days. It punishes
     small samples, noisy results and slow trades that block your 3 slots.
  4. Plateau selection: each combo is scored by the AVERAGE of itself and
     its grid neighbours, so we pick a stable region, not a lucky spike.
  5. Minimum sample: combos with < 30 trades in a training window are ignored.
  6. Adoption gate: tuned params are only used live if the tuning process
     beat the default rules OUT-OF-SAMPLE (edge/day 10%+ better, profitable
     after costs, profit factor > 1) AND a 60-run Monte-Carlo simulation of
     your actual capital agrees. Otherwise defaults stay.
  6b. Stickiness: live params only change when a new combo is clearly
     (15%+) better, so the rules don't flip-flop week to week.
  7. Edge check: if neither tuned nor default rules made money out-of-sample,
     params.json says so and main.py pauses new BUY alerts (open positions
     are still tracked) until a later weekly run finds an edge again.
"""

import argparse
import itertools
import json
import math
import os
from datetime import timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

from rules import DEFAULT_PARAMS, PARAMS_PATH, add_indicators, score_frame, HERE
from universe import sector_of
from tracker import today_ist

COST_PCT = 0.30
TRAIN_DAYS = 730      # ~2 years calendar
TEST_DAYS = 182       # ~6 months calendar
MIN_TRADES_TRAIN = 30
ADOPT_MARGIN = 0.10       # tuned OOS edge/day must beat default by >= 10%
STICKY_TOL = 0.15         # only switch params if the new best is >15% better
SEL_SEEDS = 5             # shuffled selections averaged per combo

GRID = {
    "min_score": [50, 60, 70],
    "stop_atr": [1.0, 1.5, 2.0],
    "target_atr": [2.0, 3.0, 4.0],
    "trail_atr": [0.0, 2.0, 3.0],     # 0 = no trailing stop
    "regime_filter": [0, 1],          # stand aside when NIFTY is weak?
    "rs_filter": [0, 1],              # only buy stocks beating the index?
}
GRID_KEYS = list(GRID)


# --------------------------------------------------------------------------- #
# Trade generation
# --------------------------------------------------------------------------- #
def prepare(prices: Dict[str, pd.DataFrame], index_df: pd.DataFrame = None,
            rs_lookback: int = 63) -> Dict[str, dict]:
    prepped = {}
    for t, df in prices.items():
        if len(df) < 120:
            continue
        ind = add_indicators(df, index_df=index_df, rs_lookback=rs_lookback)
        prepped[t] = {
            "ind": ind,
            "dates": ind.index.values,
            "open": ind["Open"].values.astype(float),
            "high": ind["High"].values.astype(float),
            "low": ind["Low"].values.astype(float),
            "close": ind["Close"].values.astype(float),
            "atr": ind["ATR14"].values.astype(float),
        }
    return prepped


def generate_trades(prepped: Dict[str, dict], p: dict) -> pd.DataFrame:
    rows = []
    hold = int(p["max_hold_days"])
    trail = float(p.get("trail_atr", 0) or 0)
    for t, d in prepped.items():
        score = score_frame(d["ind"], p).values
        n = len(score)
        o, h, l, c, a, dates = d["open"], d["high"], d["low"], d["close"], d["atr"], d["dates"]
        sector = sector_of(t)
        next_free = 0
        for i in np.flatnonzero(score >= p["min_score"]):
            e = i + 1
            if i < next_free or e >= n or not np.isfinite(a[i]) or a[i] <= 0:
                continue
            entry = o[e]
            atr_e = a[i]                       # ATR known at signal time only
            stop0 = entry - p["stop_atr"] * atr_e
            target = entry + p["target_atr"] * atr_e
            if stop0 <= 0:
                continue
            last = e + hold - 1
            if last >= n:            # trade would still be open at end of data
                break
            seg = slice(e, last + 1)
            op, hi, lo, cl = o[seg], h[seg], l[seg], c[seg]

            if trail > 0:
                # stop for day k uses the highest CLOSE up to day k-1 only
                cummax_prev = np.concatenate(([np.nan], np.maximum.accumulate(cl)[:-1]))
                trailed = cummax_prev - trail * atr_e
                stop_seq = np.where(np.isnan(trailed), stop0, np.maximum(stop0, trailed))
            else:
                stop_seq = np.full(len(op), stop0)

            gap_stop = op <= stop_seq
            gap_tgt = op >= target
            hit_stop = lo <= stop_seq
            hit_tgt = hi >= target
            any_hit = gap_stop | gap_tgt | hit_stop | hit_tgt
            if any_hit.any():
                k = int(np.argmax(any_hit))
                x = e + k
                trailed_up = stop_seq[k] > stop0 + 1e-9
                if gap_stop[k]:
                    exit_px = op[k]
                    status = "TRAIL_STOP" if trailed_up else "STOP_HIT"
                elif gap_tgt[k]:
                    exit_px, status = op[k], "TARGET_HIT"
                elif hit_stop[k]:
                    exit_px = stop_seq[k]
                    status = "TRAIL_STOP" if trailed_up else "STOP_HIT"
                else:
                    exit_px, status = target, "TARGET_HIT"
            else:
                x, exit_px, status = last, c[last], "EXPIRED"
            rows.append((t.replace(".NS", ""), sector, dates[i], dates[e], dates[x], entry,
                         stop0, target, exit_px, status,
                         (exit_px / entry - 1) * 100 - COST_PCT, int(score[i]), x - e + 1))
            next_free = x + 1   # no re-entry signal on the exit day (matches live)
    cols = ["ticker", "sector", "signal_date", "entry_date", "exit_date", "entry", "stop",
            "target", "exit", "status", "ret_pct", "score", "hold_days"]
    df = pd.DataFrame(rows, columns=cols)
    for col in ("signal_date", "entry_date", "exit_date"):
        df[col] = pd.to_datetime(df[col])
    return df


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def trade_metrics(tr: pd.DataFrame) -> dict:
    n = len(tr)
    if n == 0:
        return {"trades": 0}
    r = tr["ret_pct"]
    wins, losses = r[r > 0], r[r <= 0]
    std = r.std(ddof=1) if n > 1 else 0.0
    se = std / math.sqrt(n) if n > 1 else abs(r.mean())
    hold = max(tr["hold_days"].mean(), 1.0)
    return {
        "trades": n,
        "win_rate_pct": round(100 * len(wins) / n, 1),
        "avg_ret_pct": round(r.mean(), 3),
        "avg_win_pct": round(wins.mean(), 2) if len(wins) else 0.0,
        "avg_loss_pct": round(losses.mean(), 2) if len(losses) else 0.0,
        "profit_factor": round(wins.sum() / -losses.sum(), 2) if losses.sum() < 0 else None,
        "avg_hold_days": round(hold, 1),
        # average return earned per trading day the money is tied up
        "edge_per_day_pct": round(r.mean() / hold, 4),
        # same, but using a pessimistic estimate of the mean (mean - 1 std error)
        "lcb_edge_per_day_pct": round((r.mean() - se) / hold, 4),
        "target_hit_pct": round(100 * (tr["status"] == "TARGET_HIT").mean(), 1),
        "stop_hit_pct": round(100 * (tr["status"] == "STOP_HIT").mean(), 1),
        "trail_stop_pct": round(100 * (tr["status"] == "TRAIL_STOP").mean(), 1),
        "expired_pct": round(100 * (tr["status"] == "EXPIRED").mean(), 1),
    }


def objective(tr: pd.DataFrame) -> float:
    """Pessimistic edge per day of capital used. Penalises: small samples
    (bigger std error), noisy results, and slow trades that tie up one of
    your few slots for weeks."""
    if len(tr) < MIN_TRADES_TRAIN:
        return float("-inf")
    return trade_metrics(tr)["lcb_edge_per_day_pct"]


def portfolio_sim(tr: pd.DataFrame, capital: float, slots: int, risk_pct: float,
                  max_new_per_day: int = 2, seed=None, max_per_sector: int = 1) -> dict:
    """Walks trades in time order like the live bot: best score first, at most
    `max_new_per_day` new entries a day, only while slots are free; sizes each
    trade with the live rule and compounds equity. `seed` randomises the order
    of equal-score signals on the same day (for the Monte-Carlo runs)."""
    if tr.empty:
        return {"end_capital": capital, "cagr_pct": 0.0, "max_drawdown_pct": 0.0, "trades_taken": 0}
    rnd = np.random.default_rng(seed).random(len(tr)) if seed is not None else np.zeros(len(tr))
    t = tr.assign(_r=rnd).sort_values(["entry_date", "score", "_r"], ascending=[True, False, True])
    equity, peak, max_dd, taken = capital, capital, 0.0, 0
    open_pos, day, new_today = [], None, 0     # (exit_date, pnl, sector)
    for row in t.itertuples(index=False):
        if row.entry_date != day:
            day, new_today = row.entry_date, 0
        if open_pos:
            open_pos.sort(key=lambda z: z[0])
            while open_pos and open_pos[0][0] < row.entry_date:
                equity += open_pos.pop(0)[1]
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak)
        if len(open_pos) >= slots or new_today >= max_new_per_day or equity <= 0:
            continue
        row_sector = getattr(row, "sector", "?")
        if sum(1 for x in open_pos if x[2] == row_sector) >= max_per_sector:
            continue
        qty = math.floor(min(equity * risk_pct / (row.entry - row.stop), (equity / slots) / row.entry))
        if qty <= 0:
            continue
        open_pos.append((row.exit_date, qty * row.entry * row.ret_pct / 100, row_sector))
        taken += 1
        new_today += 1
    for _, pnl, _s in sorted(open_pos, key=lambda z: z[0]):
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    years = max((tr["exit_date"].max() - tr["entry_date"].min()).days / 365.25, 0.1)
    cagr = (equity / capital) ** (1 / years) - 1 if equity > 0 else -1.0
    return {"end_capital": equity, "cagr_pct": cagr * 100, "max_drawdown_pct": max_dd * 100,
            "trades_taken": taken, "years": years}


def portfolio_mc(tr: pd.DataFrame, capital: float, slots: int, risk_pct: float,
                 runs: int = 60, max_per_sector: int = 1) -> dict:
    """Which trades you actually get into depends on luck (slots full or not).
    Re-run the portfolio many times with shuffled tie-breaks and report the
    typical (median) and bad-case (worst 10%) outcomes."""
    sims = [portfolio_sim(tr, capital, slots, risk_pct, seed=s, max_per_sector=max_per_sector)
            for s in range(runs)]
    end = np.array([s["end_capital"] for s in sims])
    dd = np.array([s["max_drawdown_pct"] for s in sims])
    cagr = np.array([s["cagr_pct"] for s in sims])
    return {
        "start_capital": round(capital),
        "end_capital": int(round(float(np.median(end)))),
        "end_capital_worst10": int(round(float(np.percentile(end, 10)))),
        "cagr_pct": round(float(np.median(cagr)), 1),
        "max_drawdown_pct": round(float(np.median(dd)), 1),
        "max_drawdown_worst10_pct": round(float(np.percentile(dd, 90)), 1),
        "trades_taken": int(np.median([s["trades_taken"] for s in sims])),
        "years": round(float(sims[0].get("years", 0)), 1),
    }


def select_taken(tr: pd.DataFrame, slots: int, max_new_per_day: int, seed: int,
                 max_per_sector: int = 1) -> pd.DataFrame:
    """The trades you'd ACTUALLY take: with few slots you only get into a small
    fraction of signals (the best-scored ones on days a slot is free).
    Tuning must be judged on these, not on the average signal."""
    if tr.empty:
        return tr
    rnd = np.random.default_rng(seed).random(len(tr))
    t = tr.assign(_r=rnd).sort_values(["entry_date", "score", "_r"], ascending=[True, False, True])
    keep, open_pos, day, new_today = [], [], None, 0
    sec = t["sector"].values if "sector" in t else np.array(["?"] * len(t))
    for idx, ed, xd, sc in zip(t.index, t["entry_date"].values, t["exit_date"].values, sec):
        if ed != day:
            day, new_today = ed, 0
        open_pos = [x for x in open_pos if x[0] >= ed]
        if len(open_pos) >= slots or new_today >= max_new_per_day:
            continue
        if sum(1 for x in open_pos if x[1] == sc) >= max_per_sector:
            continue          # already holding this sector
        open_pos.append((xd, sc))
        keep.append(idx)
        new_today += 1
    return tr.loc[keep]


# --------------------------------------------------------------------------- #
# Walk-forward optimisation
# --------------------------------------------------------------------------- #
def combos():
    for vals in itertools.product(*(GRID[k] for k in GRID_KEYS)):
        yield vals


def params_for(vals) -> dict:
    p = dict(DEFAULT_PARAMS)
    p.update(dict(zip(GRID_KEYS, vals)))
    return p


def neighbours(vals):
    idx = [GRID[k].index(v) for k, v in zip(GRID_KEYS, vals)]
    out = [vals]
    for d in range(len(GRID_KEYS)):
        for step in (-1, 1):
            j = idx[d] + step
            if 0 <= j < len(GRID[GRID_KEYS[d]]):
                nv = list(vals)
                nv[d] = GRID[GRID_KEYS[d]][j]
                out.append(tuple(nv))
    return out


def in_window(tr, start, end):
    return tr[(tr["entry_date"] >= start) & (tr["entry_date"] < end)]


def raw_scores(all_taken: dict, start, end) -> dict:
    """Objective per combo, averaged over the shuffled selections."""
    out = {}
    for v, sets in all_taken.items():
        vals = [objective(in_window(s, start, end)) for s in sets]
        out[v] = float(np.mean(vals)) if all(np.isfinite(vals)) else float("-inf")
    return out


def smoothed_scores(all_taken: dict, start, end) -> dict:
    """Plateau scoring: each combo = mean of itself + its grid neighbours."""
    raw = raw_scores(all_taken, start, end)
    finite = [x for x in raw.values() if np.isfinite(x)]
    floor = min(finite) if finite else 0.0     # too-few-trades neighbours count as the worst
    out = {}
    for v in all_taken:
        if not np.isfinite(raw[v]):
            out[v] = float("-inf")
            continue
        out[v] = float(np.mean([raw[nb] if np.isfinite(raw[nb]) else floor for nb in neighbours(v)]))
    return out


def pick_best(all_taken: dict, start, end, current=None):
    sm = smoothed_scores(all_taken, start, end)
    best = max(sm, key=sm.get)
    # stickiness: keep the current params unless the new best is clearly better
    if current in sm and np.isfinite(sm[current]) and np.isfinite(sm[best]):
        if sm[current] >= sm[best] - STICKY_TOL * abs(sm[best]):
            return current
    return best


def current_live_combo():
    try:
        with open(PARAMS_PATH) as f:
            p = json.load(f)["params"]
        vals = tuple(p[k] for k in GRID_KEYS)
        return vals if all(v in GRID[k] for k, v in zip(GRID_KEYS, vals)) else None
    except Exception:
        return None


def walk_forward(prepped: dict, capital: float, slots: int, risk_pct: float,
                 max_new_per_day: int = 2, max_per_sector: int = 1) -> dict:
    default_vals = tuple(DEFAULT_PARAMS[k] for k in GRID_KEYS)
    print(f"[bt] generating trades for {len(list(combos()))} parameter combos...")
    all_taken, _cache = {}, {}
    for v in combos():
        tr = generate_trades(prepped, params_for(v))
        all_taken[v] = [select_taken(tr, slots, max_new_per_day, s, max_per_sector)
                        for s in range(SEL_SEEDS)]
        if v == default_vals:
            _cache[v] = tr        # keep only the baseline; others regenerated if needed

    def full_trades(v):
        """Full trade list for one combo (only the few we actually report on)."""
        if v not in _cache:
            _cache[v] = generate_trades(prepped, params_for(v))
        return _cache[v]

    first = min(d["ind"].index[60] for d in prepped.values())
    last = max(d["ind"].index[-1] for d in prepped.values())
    folds, s = [], first
    while s + timedelta(days=TRAIN_DAYS + 30) < last:
        tr_end = s + timedelta(days=TRAIN_DAYS)
        te_end = min(tr_end + timedelta(days=TEST_DAYS), last + timedelta(days=1))
        folds.append((s, tr_end, te_end))
        s += timedelta(days=TEST_DAYS)
    if not folds:
        raise SystemExit("Not enough history for walk-forward -- use --years 5 or more.")

    fold_rows, oos_tuned, oos_default, prev = [], [], [], default_vals
    oos_tuned_all, oos_default_all = [], []
    for (a, b, c) in folds:
        best = pick_best(all_taken, a, b, current=prev)   # same stickiness as live
        prev = best
        is_m = trade_metrics(in_window(all_taken[best][0], a, b))
        oos = in_window(all_taken[best][0], b, c)
        oos_d = in_window(all_taken[default_vals][0], b, c)
        oos_m, oos_dm = trade_metrics(oos), trade_metrics(oos_d)
        oos_tuned.append(oos)
        oos_default.append(oos_d)
        oos_tuned_all.append(in_window(full_trades(best), b, c))
        oos_default_all.append(in_window(full_trades(default_vals), b, c))
        fold_rows.append({
            "train": f"{a:%Y-%m}..{b:%Y-%m}", "test": f"{b:%Y-%m}..{c:%Y-%m}",
            "chosen": dict(zip(GRID_KEYS, best)),
            "is_epd": is_m.get("edge_per_day_pct"), "is_win": is_m.get("win_rate_pct"),
            "oos_trades": oos_m.get("trades", 0), "oos_avg_ret": oos_m.get("avg_ret_pct"),
            "oos_epd": oos_m.get("edge_per_day_pct"), "oos_win": oos_m.get("win_rate_pct"),
            "default_oos_epd": oos_dm.get("edge_per_day_pct"),
            "default_oos_win": oos_dm.get("win_rate_pct"),
        })
        print(f"[bt] fold {fold_rows[-1]['test']}: {fold_rows[-1]['chosen']} "
              f"edge/day IS {is_m.get('edge_per_day_pct')}% -> OOS {oos_m.get('edge_per_day_pct')}%")

    tuned = pd.concat(oos_tuned, ignore_index=True)
    default = pd.concat(oos_default, ignore_index=True)
    tuned_m, default_m = trade_metrics(tuned), trade_metrics(default)
    # capital sims re-select from ALL out-of-sample signals, with shuffled tie-breaks
    port_t = portfolio_mc(pd.concat(oos_tuned_all, ignore_index=True), capital, slots, risk_pct,
                          max_per_sector=max_per_sector)
    port_d = portfolio_mc(pd.concat(oos_default_all, ignore_index=True), capital, slots, risk_pct,
                          max_per_sector=max_per_sector)

    # final live params: tune on the most recent 2 years, sticky to what's live now
    live_now = current_live_combo() or default_vals
    final_best = pick_best(all_taken, last - timedelta(days=TRAIN_DAYS),
                           last + timedelta(days=1), current=live_now)
    final_params = params_for(final_best)

    is_e = [f["is_epd"] for f in fold_rows if f["is_epd"] is not None]
    oos_e = [f["oos_epd"] for f in fold_rows if f["oos_epd"] is not None]
    is_mean = float(np.mean(is_e)) if is_e else 0.0
    oos_mean = float(np.mean(oos_e)) if oos_e else 0.0
    changes = sum(1 for i in range(1, len(fold_rows)) if fold_rows[i]["chosen"] != fold_rows[i - 1]["chosen"])

    t_epd = float(tuned_m.get("edge_per_day_pct", -99)) if tuned_m.get("trades") else -99.0
    d_epd = float(default_m.get("edge_per_day_pct", -99)) if default_m.get("trades") else -99.0
    needed = d_epd * (1 + ADOPT_MARGIN) if d_epd > 0 else d_epd + 1e-9
    checks = {
        "enough trades": tuned_m.get("trades", 0) >= MIN_TRADES_TRAIN,
        "profitable after costs": tuned_m.get("avg_ret_pct", -1) > 0,
        "profit factor > 1": (tuned_m.get("profit_factor") or 0) > 1.0,
        f"edge/day beats defaults by {int(ADOPT_MARGIN * 100)}%+": t_epd >= needed,
        "capital simulation agrees": port_t["end_capital"] >= port_d["end_capital"],
    }
    adopt = bool(all(checks.values()))
    failed = [k for k, ok in checks.items() if not ok]
    if adopt:
        reason = (f"Self-tuned rules adopted: beat defaults on unseen data "
                  f"(edge {t_epd:.3f}%/day vs {d_epd:.3f}%/day; typical capital "
                  f"₹{port_t['end_capital']:,} vs ₹{port_d['end_capital']:,}).")
        live = final_params
    else:
        reason = "Kept default rules — self-tuning failed: " + ", ".join(failed) + "."
        live = dict(DEFAULT_PARAMS)
    edge_ok = bool(max(t_epd, d_epd) > 0 and max(tuned_m.get("avg_ret_pct", -1),
                                                  default_m.get("avg_ret_pct", -1)) > 0)

    return {
        "folds": fold_rows, "checks": checks,
        "oos_tuned": tuned_m, "oos_default": default_m,
        "portfolio_tuned": port_t, "portfolio_default": port_d,
        "overfit": {
            "in_sample_epd": round(is_mean, 4),
            "out_of_sample_epd": round(oos_mean, 4),
            "oos_retention_pct": round(100 * oos_mean / is_mean) if is_mean > 0 else None,
            "param_changes_between_folds": changes,
            "folds": len(fold_rows),
        },
        "adopted": adopt, "reason": reason, "edge_ok": edge_ok,
        "live_params": live, "final_tuned_candidate": final_params,
        "oos_trades_df": tuned if adopt else default,
    }


def ab_test(prepped: dict, slots: int, max_new_per_day: int, max_per_sector: int) -> list:
    """Does each new idea actually help? Same default rules, one switch changed
    at a time, measured on the trades you'd really have taken."""
    variants = [
        ("Default rules (all upgrades on)", {}),
        ("without market-regime filter", {"regime_filter": 0}),
        ("without relative-strength filter", {"rs_filter": 0}),
        ("without trailing stop", {"trail_atr": 0.0}),
        ("without sector cap (3 per sector allowed)", {"_sector": 3}),
    ]
    rows = []
    for label, override in variants:
        p = dict(DEFAULT_PARAMS)
        sec_cap = override.pop("_sector", max_per_sector)
        p.update(override)
        tr = generate_trades(prepped, p)
        taken = select_taken(tr, slots, max_new_per_day, 0, sec_cap)
        m = trade_metrics(taken)
        m["label"] = label
        rows.append(m)
    return rows


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def write_outputs(res: dict, years: int) -> str:
    live = res["live_params"]
    used = res["oos_tuned"] if res["adopted"] else res["oos_default"]
    with open(PARAMS_PATH, "w") as f:
        json.dump({
            "generated": today_ist().isoformat(),
            "adopted_tuned": res["adopted"],
            "edge_ok": res["edge_ok"],
            "reason": res["reason"],
            "params": live,
            "oos_win_rate_pct": used.get("win_rate_pct"),
            "oos_avg_ret_pct": used.get("avg_ret_pct"),
        }, f, indent=2, default=float)
    res["oos_trades_df"].to_csv(os.path.join(HERE, "backtest_trades.csv"), index=False)

    def mrow(name, m, pf):
        return (f"| {name} | {m.get('trades', 0)} | {m.get('win_rate_pct', '-')}% | "
                f"{m.get('avg_ret_pct', '-')}% | {m.get('avg_win_pct', '-')}% / {m.get('avg_loss_pct', '-')}% | "
                f"{m.get('avg_hold_days', '-')}d | {m.get('edge_per_day_pct', '-')}% | {m.get('profit_factor', '-')} |")

    def prow(name, pf):
        return (f"| {name} | ₹{pf['start_capital']:,} → ₹{pf['end_capital']:,} | ₹{pf['end_capital_worst10']:,} | "
                f"{pf['cagr_pct']}% | {pf['max_drawdown_pct']}% | {pf['max_drawdown_worst10_pct']}% | "
                f"{pf['trades_taken']} |")

    o = res["overfit"]
    lines = [
        f"# Backtest report — {today_ist():%d %b %Y}",
        "",
        f"**Decision:** {res['reason']}",
        "",
        ("**⚠️ No edge detected:** neither the tuned nor the default rules made money on unseen "
         "data after costs. New BUY alerts are paused until a later weekly run finds an edge."
         if not res["edge_ok"] else "**Edge check:** passed (profitable on unseen data after costs)."),
        "",
        f"History: ~{years} years, {o['folds']} walk-forward folds (train on 2 years → test on the "
        "next 6 months the tuner never saw, then slide forward). Everything below is from the "
        "unseen test periods only.",
        "",
        "## Trades you would actually have taken (unseen data, after 0.30% costs)",
        "",
        "| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |",
        "|---|---|---|---|---|---|---|---|",
        mrow("Self-tuned", res["oos_tuned"], res["portfolio_tuned"]),
        mrow("Default", res["oos_default"], res["portfolio_default"]),
        "",
        f"## Your capital, simulated (3 slots, live sizing rules, compounding, {res['portfolio_tuned']['years']} years)",
        "",
        "Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.",
        "",
        "| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |",
        "|---|---|---|---|---|---|---|",
        prow("Self-tuned", res["portfolio_tuned"]),
        prow("Default", res["portfolio_default"]),
        "",
        "## Do the upgrades help? (whole history, trades actually taken)",
        "",
        "One switch changed at a time, everything else at defaults. Not walk-forward,",
        "so read it as a sanity check, not proof.",
        "",
        "| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |",
        "|---|---|---|---|---|---|",
    ] + [
        f"| {r['label']} | {r.get('trades', 0)} | {r.get('win_rate_pct', '-')}% | "
        f"{r.get('avg_ret_pct', '-')}% | {r.get('edge_per_day_pct', '-')}% | {r.get('profit_factor', '-')} |"
        for r in res.get("ab", [])
    ] + [
        "",
        "## Adoption checks",
        "",
    ] + [f"- {'✅' if ok else '❌'} {k}" for k, ok in res["checks"].items()] + [
        "",
        "## Overfitting check",
        "",
        f"- Edge per day in training windows: {o['in_sample_epd']}%",
        f"- Edge per day in the unseen windows right after: {o['out_of_sample_epd']}%",
        f"- Retention: {o['oos_retention_pct']}% "
        "(70%+ is healthy; under ~40% means the tuner is mostly fitting noise)",
        f"- Parameter changes between folds: {o['param_changes_between_folds']} of {o['folds'] - 1} "
        "(frequent flipping = unstable, less trustworthy)",
        "",
        "## Live parameters now in use",
        "",
        "```json",
        json.dumps(live, indent=2, default=float),
        "```",
        "",
        "## Fold by fold",
        "",
        "| Train | Test | Chosen params | Train edge/day | Test trades | Test avg/trade | Test win | Test edge/day | Default test edge/day |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for f in res["folds"]:
        ch = ", ".join(f"{k}={v}" for k, v in f["chosen"].items())
        lines.append(f"| {f['train']} | {f['test']} | {ch} | {f['is_epd']}% | {f['oos_trades']} | "
                     f"{f['oos_avg_ret']}% | {f['oos_win']}% | {f['oos_epd']}% | {f['default_oos_epd']}% |")
    lines += [
        "",
        "## Caveats",
        "- Survivorship bias: the stock list is today's large caps, which by definition survived. "
        "Real past results would have been somewhat worse.",
        "- Fills assume you buy at the next open and your stop/target orders fill at their price; "
        "slippage on fast days can be worse.",
        "- Past performance does not guarantee future results.",
    ]
    report = "\n".join(lines)
    with open(os.path.join(HERE, "backtest_report.md"), "w") as f:
        f.write(report)
    return report


def telegram_summary(res: dict) -> str:
    m = res["oos_tuned"] if res["adopted"] else res["oos_default"]
    pf = res["portfolio_tuned"] if res["adopted"] else res["portfolio_default"]
    o = res["overfit"]
    head = "🧪 <b>Weekly backtest</b>"
    if not res["edge_ok"]:
        head += "\n⚠️ No edge found on unseen data — new BUY alerts paused."
    return (
        f"{head}\n{res['reason']}\n\n"
        f"On unseen data: {m.get('trades', 0)} trades, win rate {m.get('win_rate_pct')}%, "
        f"avg {m.get('avg_ret_pct')}%/trade after costs, avg hold {m.get('avg_hold_days')} days\n"
        f"₹{pf['start_capital']:,} → ₹{pf['end_capital']:,} typical "
        f"(bad luck ₹{pf['end_capital_worst10']:,}) over {pf['years']}y, "
        f"max drawdown {pf['max_drawdown_pct']}%\n"
        f"Overfit check: {o['oos_retention_pct']}% of training edge held up on unseen data."
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=6)
    ap.add_argument("--no-optimize", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    from data import download
    from universe import NIFTY_UNIVERSE
    from settings import load_config
    cfg = load_config()

    print(f"[bt] downloading ~{args.years}y of daily data for {len(NIFTY_UNIVERSE)} stocks...")
    prices = download(NIFTY_UNIVERSE, period=f"{args.years}y", interval="1d")
    from data import index_history
    index_df = index_history(period=f"{args.years}y")
    if index_df is None or index_df.empty:
        print("[bt] WARNING: NIFTY index data unavailable -- regime/relative-strength "
              "filters will be treated as always-true for this run.")
    prepped = prepare(prices, index_df, DEFAULT_PARAMS["rs_lookback"])
    print(f"[bt] usable stocks: {len(prepped)}")

    if args.no_optimize:
        from rules import load_params
        p = load_params()
        tr = generate_trades(prepped, p)
        print(json.dumps(trade_metrics(tr), indent=2))
        print(json.dumps(portfolio_mc(tr, cfg["capital"], cfg["max_open_positions"],
                                      cfg["risk_pct_per_trade"]), indent=2))
        return

    slots, mnpd = cfg["max_open_positions"], cfg.get("max_new_signals_per_run", 2)
    sec_cap = cfg.get("max_per_sector", 1)
    res = walk_forward(prepped, cfg["capital"], slots, cfg["risk_pct_per_trade"], mnpd, sec_cap)
    print("[bt] A/B testing the upgrades...")
    res["ab"] = ab_test(prepped, slots, mnpd, sec_cap)
    print(write_outputs(res, args.years))
    if not args.no_notify:
        from notify import send_message
        send_message(telegram_summary(res))


if __name__ == "__main__":
    main()
