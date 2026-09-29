"""
Strategy lab: puts many strategy ideas through ONE honest test and ranks them.

    python3 lab.py                 # full run (8 years of data, 3 ML seeds)
    python3 lab.py --seeds 5       # more random seeds for the ML models
    python3 lab.py --synthetic     # offline self-test on fake prices

On GitHub: Actions -> "Strategy lab" -> Run workflow (takes 20-45 minutes).
Writes lab_report.md + lab_results.csv and sends a Telegram summary.

WHAT GETS TESTED
  A. Your bot's current rules (the baseline to beat).
  B. Well-known rule strategies, incl. ones used by popular open-source NSE
     tools (PKScreener's Minervini trend template, nse-trading-lab's
     Supertrend / Bollinger / SMA-crossover / momentum), turtle breakouts,
     RSI(2) mean reversion, 12-1 momentum rotation.
  C. "Natural pattern" ideas: Fibonacci retracement pullbacks, moving-average
     crossovers whose lookbacks are Fibonacci numbers vs prime numbers vs
     round numbers vs random numbers, Fourier-cycle timing, Gaussian-smoothed
     trend turns, Laplacian (curvature) turns, Hurst-exponent trend regime.
  D. Machine learning: logistic regression, Gaussian naive Bayes, random
     forest, gradient boosting and a small neural net, trained walk-forward
     (only on the past, retrained every 6 months) on ~35 features incl. all
     of the above (Fourier, Gaussian, Laplacian, Fibonacci, Hurst, skew,
     kurtosis, regression angle). Each random model is run with several
     random seeds; we report the average and the spread.
  E. Controls: random entries (many seeds) with the same exits = what pure
     luck looks like; and NIFTY 50 buy-and-hold.

HOW IT STAYS HONEST
  * Same data, same window, same costs (0.30% round trip), same entry rule
    (next day's OPEN after the signal), same capital simulation (your
    capital, slots, risk per trade, 1 stock per sector) for everything.
  * Scored only on the period AFTER the first 2 years, which the ML models
    never trained on. Rule strategies use textbook settings -- nothing is
    tuned on this data.
  * "Beats luck?" = better than 95% of the random-entry runs.
  * Split into two halves: an idea that only worked in one half is fragile.
  * Many ideas are tested, so the best one is partly lucky by construction.
    The report says how much luck alone can produce.
"""

import argparse
import math
import os
import time
from datetime import timedelta

import numpy as np
import pandas as pd

from backtest import trade_metrics, portfolio_mc, COST_PCT
from indicators import sma, rsi, macd, atr
from rules import DEFAULT_PARAMS, add_indicators, score_frame, HERE
from universe import sector_of

WARMUP = 260                      # bars needed before features are valid (SMA200, 52w high)
TRAIN_DAYS, STEP_DAYS, PURGE_DAYS = 730, 182, 35
RANDOM_SEEDS = 20                 # per exit style
MC_RUNS = 30

FIB_PAIRS = [(8, 21), (13, 34), (21, 55), (34, 89)]
PRIME_PAIRS = [(7, 23), (11, 37), (19, 53), (31, 89)]
ROUND_PAIRS = [(10, 25), (15, 35), (20, 50), (30, 90)]


# --------------------------------------------------------------------------- #
# Features (every one uses only data up to that day's close)
# --------------------------------------------------------------------------- #
def causal_gaussian(y: np.ndarray, sigma: float = 5.0) -> np.ndarray:
    k = np.arange(int(3 * sigma) + 1)
    w = np.exp(-k ** 2 / (2 * sigma ** 2))
    w /= w.sum()
    out = np.convolve(y, w)[: len(y)]
    out[: len(k) - 1] = np.nan
    return out


def rolling_linreg(y: np.ndarray, w: int):
    """slope per bar and R^2 of a straight-line fit to the last w values."""
    n = len(y)
    s = pd.Series(y)
    j = pd.Series(np.arange(n, dtype=float))
    sy = s.rolling(w).sum()
    sjy = (j * s).rolling(w).sum()
    start = j - (w - 1)
    sxy = sjy - start * sy                      # sum of x*y with x = 0..w-1
    xm = (w - 1) / 2
    sxx = w * (w ** 2 - 1) / 12
    slope = (sxy - xm * sy) / sxx
    vy = s.rolling(w).var(ddof=0) * w
    r2 = (slope ** 2 * sxx) / vy.replace(0, np.nan)
    return slope.values, r2.clip(0, 1).values


def rolling_fft(logc: np.ndarray, w: int = 64, keep: int = 3):
    """For each day: dominant cycle length, how strong it is, and the slope
    of a low-pass (first `keep` harmonics) reconstruction at the last bar."""
    n = len(logc)
    period = np.full(n, np.nan)
    power = np.full(n, np.nan)
    lp_slope = np.full(n, np.nan)
    if n < w + 1:
        return period, power, lp_slope
    win = np.lib.stride_tricks.sliding_window_view(logc, w)          # (n-w+1, w)
    x = np.arange(w) - (w - 1) / 2
    b = (win * x).sum(1) / (x ** 2).sum()
    det = win - win.mean(1, keepdims=True) - np.outer(b, x)          # remove linear trend
    spec = np.fft.rfft(det, axis=1)
    pw = np.abs(spec) ** 2
    band = pw[:, 1: w // 4 + 1]                                       # periods 4..64 bars
    k = band.argmax(1) + 1
    period[w - 1:] = w / k
    power[w - 1:] = band.max(1) / np.maximum(pw[:, 1:].sum(1), 1e-18)
    low = spec.copy()
    low[:, keep + 1:] = 0
    rec = np.fft.irfft(low, n=w, axis=1)
    lp_slope[w - 1:] = (rec[:, -1] - rec[:, -2]) + b
    return period, power, lp_slope


def supertrend_dir(h, l, c, a, mult=3.0):
    n = len(c)
    mid = (h + l) / 2
    ub, lb = mid + mult * a, mid - mult * a
    fu, fl = ub.copy(), lb.copy()
    d = np.ones(n)
    for i in range(1, n):
        if not (np.isfinite(ub[i]) and np.isfinite(fu[i - 1])):
            continue
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        if d[i - 1] < 0 and c[i] > fu[i - 1]:
            d[i] = 1
        elif d[i - 1] > 0 and c[i] < fl[i - 1]:
            d[i] = -1
        else:
            d[i] = d[i - 1]
    return d


def build_features(df: pd.DataFrame, idx: pd.DataFrame) -> pd.DataFrame:
    f = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    c, h, l, v = f["Close"], f["High"], f["Low"], f["Volume"]
    logc = np.log(c.values)
    f["ATR"] = atr(f, 14)
    for w in (5, 20, 50, 150, 200):
        f[f"SMA{w}"] = sma(c, w)
    f["RSI2"], f["RSI14"] = rsi(c, 2), rsi(c, 14)
    m, s, hist = macd(c)
    f["MACDH"] = hist / c
    f["VOL20"], f["VOL50"] = v.rolling(20).mean(), v.rolling(50).mean()
    f["HI20P"] = c.rolling(20).max().shift(1)          # prior 20-day closing high
    f["HI55P"] = h.rolling(55).max().shift(1)
    f["LO20P"] = l.rolling(20).min().shift(1)
    f["HI252"], f["LO252"] = h.rolling(252).max(), l.rolling(252).min()
    f["H55"], f["L55"] = h.rolling(55).max(), l.rolling(55).min()
    sd20 = c.rolling(20).std()
    f["BBU"] = f["SMA20"] + 2 * sd20

    ic = idx["Close"].reindex(f.index).ffill()
    f["REGIME"] = ((ic > sma(ic, 50)) & (sma(ic, 20) > sma(ic, 50))).astype(float)

    # --- basic ML features
    X = pd.DataFrame(index=f.index)
    for k in (1, 5, 20, 60):
        X[f"ret{k}"] = c.pct_change(k)
    for w in (20, 50, 200):
        X[f"d_sma{w}"] = c / f[f"SMA{w}"] - 1
    X["rsi14"], X["rsi2"], X["macd_h"] = f["RSI14"], f["RSI2"], f["MACDH"]
    X["atr_pct"] = f["ATR"] / c
    X["vol_ratio"] = v / f["VOL20"]
    X["d_high20"] = c / c.rolling(20).max() - 1
    X["d_high252"] = c / f["HI252"] - 1
    X["rs63"] = c.pct_change(63) - ic.pct_change(63)
    X["idx_ret20"] = ic.pct_change(20)
    X["idx_d_sma50"] = ic / sma(ic, 50) - 1
    X["idx_vol20"] = ic.pct_change().rolling(20).std()
    basic = list(X.columns)

    # --- "natural pattern" / signal-processing features
    rng55 = (f["H55"] - f["L55"]).replace(0, np.nan)
    pos = (c - f["L55"]) / rng55
    X["fib_pos55"] = pos
    levels = np.array([0.236, 0.382, 0.5, 0.618, 0.786])
    X["fib_dist"] = np.min(np.abs(pos.values[:, None] - levels[None, :]), axis=1)
    per, pw, lps = rolling_fft(logc)
    X["fft_period"], X["fft_power"], X["fft_slope"] = per, pw, lps * 100
    g = causal_gaussian(logc, 5.0)
    X["gauss_slope"] = np.r_[np.nan, np.diff(g)] * 100
    X["laplacian"] = np.r_[np.nan, np.nan, np.diff(g, 2)] * 1e4
    r1 = pd.Series(logc, index=f.index).diff()
    r10 = pd.Series(logc, index=f.index).diff(10)
    vr = r10.rolling(120).var() / (10 * r1.rolling(120).var())
    X["hurst"] = 0.5 + 0.5 * np.log(vr.clip(lower=1e-6)) / np.log(10)
    X["skew60"], X["kurt60"] = r1.rolling(60).skew(), r1.rolling(60).kurt()
    X["zscore20"] = (c - f["SMA20"]) / sd20
    slope, r2 = rolling_linreg(c.values, 20)
    X["lr_angle20"] = np.degrees(np.arctan(slope / f["ATR"].values))
    X["lr_r2_20"] = r2
    out = pd.concat([f, X], axis=1)
    out.attrs["basic"], out.attrs["all"] = basic, list(X.columns)
    return out


# --------------------------------------------------------------------------- #
# One trade simulator for every strategy
# --------------------------------------------------------------------------- #
def simulate(ticker, F, entry, score, stop_atr=1.5, target_atr=3.0, hold=22, trail_atr=0.0,
             exit_sig=None, stop_px=None, target_px=None):
    o, h, l, c, a = (F[k].values.astype(float) for k in ("Open", "High", "Low", "Close", "ATR"))
    dates = F.index.values
    n = len(c)
    sector = sector_of(ticker)
    rows, next_free = [], 0
    for i in np.flatnonzero(entry):
        e = i + 1
        if i < next_free or e >= n or not np.isfinite(a[i]) or a[i] <= 0:
            continue
        px = o[e]
        stop0 = stop_px[i] if stop_px is not None else px - stop_atr * a[i]
        tgt = (target_px[i] if target_px is not None
               else (px + target_atr * a[i] if target_atr else np.inf))
        if not (np.isfinite(stop0) and 0 < stop0 < px) or not tgt > px:
            continue
        last = e + hold - 1
        if last >= n:
            break
        seg = slice(e, last + 1)
        op, hi, lo, cl = o[seg], h[seg], l[seg], c[seg]
        if trail_atr > 0:
            prevmax = np.concatenate(([np.nan], np.maximum.accumulate(cl)[:-1]))
            st = np.where(np.isnan(prevmax), stop0, np.maximum(stop0, prevmax - trail_atr * a[i]))
        else:
            st = np.full(len(op), stop0)
        hit = (op <= st) | (op >= tgt) | (lo <= st) | (hi >= tgt)
        k_hit = int(np.argmax(hit)) if hit.any() else 10 ** 9
        k_sig = 10 ** 9
        if exit_sig is not None:
            es = exit_sig[e:last]                 # signal at close of day k -> out at open k+1
            if es.any():
                k_sig = int(np.argmax(es))
        if k_sig < k_hit and k_sig < 10 ** 9:
            x = e + k_sig + 1
            exit_px, status = o[x], "EXIT_SIGNAL"
        elif k_hit < 10 ** 9:
            k = k_hit
            x = e + k
            if op[k] <= st[k]:
                exit_px, status = op[k], "STOP_HIT"
            elif op[k] >= tgt:
                exit_px, status = op[k], "TARGET_HIT"
            elif lo[k] <= st[k]:
                exit_px, status = st[k], "STOP_HIT"
            else:
                exit_px, status = tgt, "TARGET_HIT"
        else:
            x, exit_px, status = last, c[last], "EXPIRED"
        rows.append((ticker, sector, dates[i], dates[e], dates[x], px, stop0,
                     tgt if np.isfinite(tgt) else px * 10, exit_px, status,
                     (exit_px / px - 1) * 100 - COST_PCT,
                     float(score[i]) if np.isfinite(score[i]) else 0.0, x - e + 1))
        next_free = x + 1
    return rows


COLS = ["ticker", "sector", "signal_date", "entry_date", "exit_date", "entry", "stop",
        "target", "exit", "status", "ret_pct", "score", "hold_days"]


def to_df(rows):
    df = pd.DataFrame(rows, columns=COLS)
    for col in ("signal_date", "entry_date", "exit_date"):
        df[col] = pd.to_datetime(df[col])
    return df


# --------------------------------------------------------------------------- #
# Rule strategies: each returns simulate() kwargs for one stock
# --------------------------------------------------------------------------- #
def ready(F):
    r = np.zeros(len(F), bool)
    r[WARMUP:] = True
    return r


def cross_up(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.r_[False, (a[1:] > b[1:]) & (a[:-1] <= b[:-1])]


def s_bot(F, raw):
    sc = score_frame(raw, DEFAULT_PARAMS).values.astype(float)
    return dict(entry=(sc >= DEFAULT_PARAMS["min_score"]) & ready(F), score=sc)


def s_minervini(F, raw):
    c = F["Close"]
    tt = ((c > F["SMA50"]) & (F["SMA50"] > F["SMA150"]) & (F["SMA150"] > F["SMA200"])
          & (F["SMA200"] > F["SMA200"].shift(20)) & (c >= 1.25 * F["LO252"])
          & (c >= 0.75 * F["HI252"]) & (F["rs63"] > 0))
    brk = (c > F["HI20P"]) & (F["Volume"] > 1.5 * F["VOL50"])
    return dict(entry=(tt & brk).values & ready(F), score=(F["rs63"] * 100).values,
                stop_atr=2.0, target_atr=None, trail_atr=3.0, hold=60)


def s_turtle(F, raw):
    c = F["Close"]
    return dict(entry=(c > F["HI55P"]).values & ready(F), score=F["rs63"].values * 100,
                exit_sig=(c < F["LO20P"]).values, stop_atr=2.0, target_atr=None, hold=80)


def s_rsi2(F, raw):
    c = F["Close"]
    return dict(entry=((c > F["SMA200"]) & (F["RSI2"] < 10)).values & ready(F),
                score=(100 - F["RSI2"]).values, exit_sig=(c > F["SMA5"]).values,
                stop_atr=3.0, target_atr=None, hold=10)


def s_bollinger(F, raw):
    c = F["Close"]
    ent = (c > F["BBU"]) & (F["Volume"] > 1.5 * F["VOL20"])
    return dict(entry=ent.values & ready(F), score=F["vol_ratio"].values * 10,
                exit_sig=(c < F["SMA20"]).values, stop_atr=2.0, target_atr=None, hold=40)


def s_supertrend(F, raw):
    d = supertrend_dir(*(F[k].values for k in ("High", "Low", "Close", "ATR")))
    up = np.r_[False, (d[1:] > 0) & (d[:-1] < 0)]
    return dict(entry=up & ready(F), score=F["rs63"].values * 100,
                exit_sig=d < 0, stop_atr=3.0, target_atr=None, hold=80)


def s_momentum(F, raw):
    c = F["Close"]
    idx = F.index
    month_end = np.r_[idx[1:].month != idx[:-1].month, False]
    mom = (c.shift(21) / c.shift(252) - 1).values
    ok = (c > F["SMA200"]).values & (F["REGIME"].values > 0)
    return dict(entry=month_end & ok & ready(F) & np.isfinite(mom), score=mom * 100,
                stop_atr=3.0, target_atr=None, hold=21)


def s_fib_pullback(F, raw):
    c, h55, l55 = F["Close"], F["H55"], F["L55"]
    rng = h55 - l55
    retr = (h55 - c) / rng.replace(0, np.nan)
    ent = ((F["SMA50"] > F["SMA200"]) & retr.between(0.382, 0.618)
           & (c > F["High"].shift(1)) & (rng > 2 * F["ATR"]))
    return dict(entry=ent.values & ready(F), score=(1 - F["fib_dist"]).values * 100,
                stop_px=(h55 - 0.786 * rng).values, target_px=h55.values, hold=30)


def s_gauss_turn(F, raw):
    gs = F["gauss_slope"].values
    ent = cross_up(gs, np.zeros(len(gs))) & (F["Close"] > F["SMA200"]).values
    return dict(entry=ent & ready(F), score=F["rs63"].values * 100,
                exit_sig=gs < 0, stop_atr=2.0, target_atr=None, hold=40)


def s_laplacian_turn(F, raw):
    lp, gs = F["laplacian"].values, F["gauss_slope"].values
    ent = cross_up(lp, np.zeros(len(lp))) & (gs > 0) & (F["Close"] > F["SMA200"]).values
    return dict(entry=ent & ready(F), score=F["rs63"].values * 100,
                exit_sig=gs < 0, stop_atr=2.0, target_atr=None, hold=40)


def s_fourier(F, raw):
    fs, fp = F["fft_slope"].values, F["fft_power"].values
    ent = cross_up(fs, np.zeros(len(fs))) & (fp > 0.3) & (F["Close"] > F["SMA200"]).values
    return dict(entry=ent & ready(F), score=fp * 100,
                exit_sig=fs < 0, stop_atr=2.0, target_atr=None, hold=30)


def s_bot_hurst(F, raw):
    d = s_bot(F, raw)
    d["entry"] = d["entry"] & (F["hurst"].values > 0.55)
    return d


def make_cross(fast, slow):
    def s(F, raw):
        c = F["Close"]
        f_, s_ = sma(c, fast).values, sma(c, slow).values
        return dict(entry=cross_up(f_, s_) & ready(F), score=F["rs63"].values * 100,
                    exit_sig=f_ < s_, stop_atr=2.5, target_atr=None, hold=120)
    return s


RULES = {
    "Your bot (current rules)": ("baseline", s_bot),
    "Bot + Hurst trending filter": ("natural", s_bot_hurst),
    "Minervini trend template breakout (PKScreener-style)": ("popular", s_minervini),
    "Turtle 55-day breakout": ("popular", s_turtle),
    "RSI(2) mean reversion (Connors)": ("popular", s_rsi2),
    "Bollinger breakout + volume": ("popular", s_bollinger),
    "Supertrend(10,3) flip": ("popular", s_supertrend),
    "12-1 momentum rotation (monthly)": ("popular", s_momentum),
    "Fibonacci 38-62% pullback": ("natural", s_fib_pullback),
    "Gaussian-smoothed trend turn": ("natural", s_gauss_turn),
    "Laplacian (curvature) turn": ("natural", s_laplacian_turn),
    "Fourier cycle turn": ("natural", s_fourier),
}


def cross_families(seed=7):
    fams = {"Fibonacci": FIB_PAIRS, "Prime": PRIME_PAIRS, "Round": ROUND_PAIRS}
    rng = np.random.default_rng(seed)
    rnd = []
    while len(rnd) < 4:
        a, b = sorted(rng.integers(5, 100, 2))
        if b >= a * 2:
            rnd.append((int(a), int(b)))
    fams["Random numbers"] = rnd
    return fams


# --------------------------------------------------------------------------- #
# Machine learning (walk-forward, several random seeds)
# --------------------------------------------------------------------------- #
def outcome_all(F, stop_atr=1.5, target_atr=3.0, hold=22):
    """Label for every day: what the bot-style trade opened next morning returned."""
    o, h, l, c, a = (F[k].values.astype(float) for k in ("Open", "High", "Low", "Close", "ATR"))
    n = len(c)
    ret = np.full(n, np.nan)
    xi = np.full(n, -1)
    for i in range(WARMUP, n - hold - 1):
        e = i + 1
        if not (np.isfinite(a[i]) and a[i] > 0):
            continue
        px = o[e]
        st, tg = px - stop_atr * a[i], px + target_atr * a[i]
        seg = slice(e, e + hold)
        op, hi, lo = o[seg], h[seg], l[seg]
        hit = (lo <= st) | (hi >= tg)
        if hit.any():
            k = int(np.argmax(hit))
            if op[k] <= st:
                xp = op[k]
            elif op[k] >= tg:
                xp = op[k]
            elif lo[k] <= st:
                xp = st
            else:
                xp = tg
            xi[i] = e + k
        else:
            xp, xi[i] = c[e + hold - 1], e + hold - 1
        ret[i] = (xp / px - 1) * 100 - COST_PCT
    return ret, xi


def ml_models(seed):
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import GaussianNB
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {
        "Logistic regression": (False, lambda: make_pipeline(
            StandardScaler(), LogisticRegression(C=0.1, max_iter=500))),
        "Gaussian naive Bayes": (False, lambda: make_pipeline(StandardScaler(), GaussianNB())),
        "Random forest": (True, lambda: RandomForestClassifier(
            n_estimators=120, max_depth=6, min_samples_leaf=200, max_features="sqrt",
            n_jobs=-1, random_state=seed)),
        "Gradient boosting": (True, lambda: HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
            max_features=0.5, random_state=seed)),
        "Gradient boosting (basic features only)": (True, lambda: HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
            max_features=0.5, random_state=seed)),
        "Neural network (MLP)": (True, lambda: make_pipeline(StandardScaler(), MLPClassifier(
            hidden_layer_sizes=(32, 16), alpha=1e-3, early_stopping=True, max_iter=200,
            random_state=seed))),
    }


def run_ml(feats: dict, folds, n_seeds: int, eval_start):
    """Returns {model_name: [trades_df per seed]} and feature importances."""
    basic, allf = next(iter(feats.values())).attrs["basic"], next(iter(feats.values())).attrs["all"]
    parts = []
    for t, F in feats.items():
        ret, xi = outcome_all(F)
        ok = np.isfinite(ret)
        d = F.loc[ok, allf].copy()
        d["_t"], d["_ret"] = t, ret[ok]
        d["_xd"] = F.index.values[xi[ok]]
        d["_d"] = F.index[ok]
        parts.append(d)
    D = pd.concat(parts, ignore_index=True).replace([np.inf, -np.inf], np.nan).dropna()
    D["_y"] = (D["_ret"] > 0).astype(int)
    print(f"[lab] ML dataset: {len(D):,} stock-days, {len(allf)} features, "
          f"base win rate {100 * D['_y'].mean():.1f}%")

    out, importances = {}, None
    names = list(ml_models(0))
    for name in names:
        uses_seed = ml_models(0)[name][0]
        cols = basic if "basic" in name else allf
        seeds = range(n_seeds) if uses_seed else [0]
        out[name] = []
        for sd in seeds:
            pred_parts = []
            for (a, b, c) in folds:
                tr = D[(D["_xd"] < a - np.timedelta64(1, "D")) & (D["_d"] >= a - pd.Timedelta(days=TRAIN_DAYS * 2))]
                tr = tr.iloc[:: 2]                            # overlapping labels -> thin them
                te = D[(D["_d"] >= a) & (D["_d"] < b)]
                if len(tr) < 2000 or te.empty:
                    continue
                m = ml_models(sd)[name][1]()
                m.fit(tr[cols].values, tr["_y"].values)
                p_tr = m.predict_proba(tr[cols].values)[:, 1]
                thr = np.quantile(p_tr, 0.90)                 # act on the model's top 10% calls
                p_te = m.predict_proba(te[cols].values)[:, 1]
                pred_parts.append(pd.DataFrame({"_t": te["_t"].values, "_d": te["_d"].values,
                                                "p": p_te, "sig": p_te >= thr}))
                if name == "Random forest" and sd == 0:
                    importances = pd.Series(m.feature_importances_, index=cols)
            if not pred_parts:
                continue
            P = pd.concat(pred_parts)
            rows = []
            for t, g in P.groupby("_t"):
                F = feats[t]
                ent = np.zeros(len(F), bool)
                sc = np.zeros(len(F))
                pos = F.index.get_indexer(pd.DatetimeIndex(g["_d"]))
                ent[pos] = g["sig"].values
                sc[pos] = g["p"].values * 100
                rows += simulate(t, F, ent, sc)
            out[name].append(to_df(rows))
            print(f"[lab]   {name} seed {sd}: {int(P['sig'].sum())} signals")
    return out, importances


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def evaluate(tr: pd.DataFrame, start, mid, cfg) -> dict:
    tr = tr[tr["signal_date"] >= start]
    m = trade_metrics(tr)
    if not m.get("trades"):
        return {"trades": 0}
    pf = portfolio_mc(tr, cfg["capital"], cfg["max_open_positions"], cfg["risk_pct_per_trade"],
                      runs=MC_RUNS, max_per_sector=cfg.get("max_per_sector", 1))
    h1 = tr[tr["signal_date"] < mid]["ret_pct"]
    h2 = tr[tr["signal_date"] >= mid]["ret_pct"]
    return {
        "trades": m["trades"], "win_rate_pct": m["win_rate_pct"], "avg_ret_pct": m["avg_ret_pct"],
        "profit_factor": m["profit_factor"], "avg_hold_days": m["avg_hold_days"],
        "h1_avg_ret": round(h1.mean(), 2) if len(h1) else None,
        "h2_avg_ret": round(h2.mean(), 2) if len(h2) else None,
        "cagr_pct": pf["cagr_pct"], "end_capital": pf["end_capital"],
        "end_capital_worst10": pf["end_capital_worst10"], "max_dd_pct": pf["max_drawdown_pct"],
        "trades_taken": pf["trades_taken"],
    }


def avg_seeds(results: list) -> dict:
    ok = [r for r in results if r.get("trades")]
    if not ok:
        return {"trades": 0}
    out = {}
    for k in ok[0]:
        vals = [r[k] for r in ok if r.get(k) is not None]
        out[k] = round(float(np.mean(vals)), 2) if vals else None
    cg = [r["cagr_pct"] for r in ok]
    out["cagr_spread"] = f"{min(cg):.1f}..{max(cg):.1f}" if len(ok) > 1 else ""
    out["seeds"] = len(ok)
    return out


def nifty_stats(idx: pd.DataFrame, start):
    c = idx["Close"][idx.index >= start]
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    cagr = (c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1
    dd = (1 - c / c.cummax()).max()
    return round(cagr * 100, 1), round(dd * 100, 1), yrs


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def synthetic(n_stocks=110, years=8, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=int(252 * years))
    mk = np.cumsum(rng.normal(0.0004, 0.01, len(dates)))
    from universe import NIFTY_UNIVERSE
    prices = {}
    for t in NIFTY_UNIVERSE[:n_stocks]:
        beta, drift = rng.uniform(0.6, 1.4), rng.normal(0.0002, 0.0003)
        lc = 5 + beta * mk + np.cumsum(rng.normal(drift, 0.015, len(dates)))
        c = np.exp(lc)
        o = c * np.exp(rng.normal(0, 0.005, len(dates)))
        hi = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.008, len(dates))))
        lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.008, len(dates))))
        vol = rng.lognormal(13, 0.4, len(dates))
        prices[t] = pd.DataFrame({"Open": o, "High": hi, "Low": lo, "Close": c, "Volume": vol},
                                 index=dates)
    idx = pd.DataFrame({"Close": np.exp(9 + mk)}, index=dates)
    idx["Open"] = idx["High"] = idx["Low"] = idx["Close"]
    idx["Volume"] = 0
    return prices, idx


def fmt_money(x):
    return f"₹{int(x):,}" if x is not None and np.isfinite(x) else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=8)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--no-ml", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--stocks", type=int, default=0, help="limit stock count (testing)")
    args = ap.parse_args()
    t0 = time.time()

    from settings import load_config
    cfg = load_config()

    if args.synthetic:
        prices, idx = synthetic(args.stocks or 110, args.years)
    else:
        from data import download, index_history
        from universe import NIFTY_UNIVERSE
        uni = NIFTY_UNIVERSE[: args.stocks] if args.stocks else NIFTY_UNIVERSE
        print(f"[lab] downloading {args.years}y of daily data for {len(uni)} stocks...")
        prices = download(uni, period=f"{args.years}y", interval="1d")
        idx = index_history(period=f"{args.years}y")
        if idx is None or idx.empty:
            raise SystemExit("NIFTY index data unavailable -- try again later.")

    feats, raws = {}, {}
    for t, df in prices.items():
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        df = df[(df["Close"] > 0) & (df["Open"] > 0)]
        if len(df) < WARMUP + 300:
            continue
        name = t.replace(".NS", "")
        feats[name] = build_features(df, idx)
        raws[name] = add_indicators(df, index_df=idx, rs_lookback=DEFAULT_PARAMS["rs_lookback"])
    print(f"[lab] usable stocks: {len(feats)}  ({time.time() - t0:.0f}s)")

    first = min(F.index[WARMUP] for F in feats.values())
    last = max(F.index[-1] for F in feats.values())
    eval_start = first + timedelta(days=TRAIN_DAYS)
    mid = eval_start + (last - eval_start) / 2
    folds, s = [], eval_start
    while s < last:
        folds.append((s, min(s + timedelta(days=STEP_DAYS), last + timedelta(days=1)), None))
        s += timedelta(days=STEP_DAYS)
    print(f"[lab] scoring window {eval_start:%Y-%m-%d} .. {last:%Y-%m-%d}")

    def run_rule(fn):
        rows = []
        for t, F in feats.items():
            kw = fn(F, raws[t])
            rows += simulate(t, F, **kw)
        return to_df(rows)

    results = []   # dicts with name, group, metrics

    for name, (grp, fn) in RULES.items():
        r = evaluate(run_rule(fn), eval_start, mid, cfg)
        results.append({"name": name, "group": grp, **r})
        print(f"[lab] {name}: {r.get('trades', 0)} trades, CAGR {r.get('cagr_pct')}%")

    fam_rows = []
    for fam, pairs in cross_families().items():
        for fa, sl in pairs:
            r = evaluate(run_rule(make_cross(fa, sl)), eval_start, mid, cfg)
            fam_rows.append({"family": fam, "pair": f"{fa}/{sl}", **r})
    fam_df = pd.DataFrame(fam_rows)
    for fam, g in fam_df.groupby("family", sort=False):
        results.append({"name": f"SMA crossover — {fam} lookbacks ({', '.join(g['pair'])})",
                        "group": "numbers", **avg_seeds(g.drop(columns=["family", "pair"]).to_dict("records"))})
    print(f"[lab] crossover families done ({time.time() - t0:.0f}s)")

    # random-entry controls
    # Two exit styles, because "let winners run" exits behave differently from
    # fixed targets even with random entries; the luck line uses the tougher one.
    rnd_cagr, rnd_avg, p95s = [], [], []
    styles = {"fixed target": {}, "trailing": dict(stop_atr=2.0, target_atr=None, trail_atr=3.0, hold=60)}
    for style, kw in styles.items():
        cg = []
        for sd in range(RANDOM_SEEDS):
            rng = np.random.default_rng(1000 + sd)
            rows = []
            for t, F in feats.items():
                ent = (rng.random(len(F)) < 0.02) & ready(F)
                rows += simulate(t, F, ent, rng.random(len(F)) * 100, **kw)
            r = evaluate(to_df(rows), eval_start, mid, cfg)
            cg.append(r["cagr_pct"])
            rnd_avg.append(r["avg_ret_pct"])
        p95s.append(float(np.percentile(cg, 95)))
        rnd_cagr += cg
    luck95 = max(p95s)
    luck = {"median": float(np.median(rnd_cagr)), "p95": luck95, "max": float(np.max(rnd_cagr)),
            "min": float(np.min(rnd_cagr)), "avg_ret_median": float(np.median(rnd_avg))}
    results.append({"name": f"Random entries ({2 * RANDOM_SEEDS} runs, median)", "group": "control",
                    "cagr_pct": round(luck["median"], 1), "avg_ret_pct": round(luck["avg_ret_median"], 3)})
    print(f"[lab] random baseline: median CAGR {luck['median']:.1f}%, 95th pct {luck95:.1f}% "
          f"({time.time() - t0:.0f}s)")

    importances = None
    if not args.no_ml:
        ml, importances = run_ml(feats, folds, args.seeds, eval_start)
        for name, dfs in ml.items():
            res = [evaluate(d, eval_start, mid, cfg) for d in dfs]
            results.append({"name": f"ML: {name}", "group": "ml", **avg_seeds(res)})
        print(f"[lab] ML done ({time.time() - t0:.0f}s)")

    n_cagr, n_dd, yrs = nifty_stats(idx, eval_start)
    results.append({"name": "NIFTY 50 buy-and-hold", "group": "control", "cagr_pct": n_cagr,
                    "max_dd_pct": n_dd})

    R = pd.DataFrame(results)
    R["beats_luck"] = R["cagr_pct"] > luck95
    R["beats_nifty"] = R["cagr_pct"] > n_cagr
    R = R.sort_values("cagr_pct", ascending=False, na_position="last")
    R.to_csv(os.path.join(HERE, "lab_results.csv"), index=False)
    fam_df.to_csv(os.path.join(HERE, "lab_crossovers.csv"), index=False)

    report = write_report(R, fam_df, luck, n_cagr, n_dd, yrs, eval_start, last, cfg,
                          importances, len(feats), args, time.time() - t0)
    print(report)
    if not args.no_notify and not args.synthetic:
        from notify import send_message
        send_message(telegram_text(R, luck, n_cagr, yrs))


def write_report(R, fam_df, luck, n_cagr, n_dd, yrs, start, last, cfg, imp, n_stocks, args, secs):
    L = [f"# Strategy lab — {pd.Timestamp.today():%Y-%m-%d}", "",
         f"{n_stocks} NSE stocks, scored on **{start:%b %Y} – {last:%b %Y}** ({yrs:.1f} years) "
         f"with your settings: ₹{int(cfg['capital']):,} capital, {cfg['max_open_positions']} slots, "
         f"{cfg['risk_pct_per_trade'] * 100:.0f}% risk per trade, 0.30% costs per trade."
         + (" **SYNTHETIC TEST DATA — numbers mean nothing.**" if args.synthetic else ""), "",
         "## Yardsticks", "",
         f"- **NIFTY 50 buy-and-hold:** {n_cagr}% a year (worst fall {n_dd}%).",
         f"- **Pure luck** (random entries, {2 * RANDOM_SEEDS} runs with fixed-target and trailing exits): median "
         f"{luck['median']:.1f}% a year; 95% of random runs stayed below **{luck['p95']:.1f}%** "
         f"(the 'luck line'); "
         f"the single luckiest run made {luck['max']:.1f}%.",
         "- A strategy is only interesting if it beats **both**.", "",
         "## Ranking (by typical yearly growth of your capital)", "",
         "| # | Strategy | Type | Trades | Win % | Avg/trade | 1st half | 2nd half | Yearly growth | Bad-luck ₹ | Worst fall | Beats luck | Beats Nifty |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(R.itertuples(index=False), 1):
        g = lambda k: getattr(r, k, None)
        def num(k, suf=""):
            v = g(k)
            if v is None or (isinstance(v, float) and not np.isfinite(v)):
                return "-"
            if k == "trades":
                v = int(round(v))
            return f"{v}{suf}"
        spread = g("cagr_spread")
        growth = num("cagr_pct", "%") + (f" ({spread})" if isinstance(spread, str) and spread else "")
        L.append(f"| {i} | {r.name} | {r.group} | {num('trades')} | {num('win_rate_pct')} | "
                 f"{num('avg_ret_pct', '%')} | {num('h1_avg_ret', '%')} | {num('h2_avg_ret', '%')} | "
                 f"{growth} | {fmt_money(g('end_capital_worst10')) if g('end_capital_worst10') else '-'} | "
                 f"{num('max_dd_pct', '%')} | {'✅' if r.beats_luck else '—'} | {'✅' if r.beats_nifty else '—'} |")
    L += ["", "Yearly growth for ML models is the average over random seeds, with the range "
          "across seeds in brackets. 1st/2nd half = average return per trade in each half of "
          "the window; if one is negative the idea is fragile.", "",
          "## Do Fibonacci / prime numbers matter? (SMA crossovers)", "",
          "| Family | Pair | Trades | Avg/trade | Yearly growth |", "|---|---|---|---|---|"]
    for r in fam_df.itertuples(index=False):
        L.append(f"| {r.family} | {r.pair} | {r.trades} | {getattr(r, 'avg_ret_pct', '-')}% | "
                 f"{getattr(r, 'cagr_pct', '-')}% |")
    L += ["", "If the Fibonacci and prime rows look no better than the round and random-number "
          "rows, the 'special numbers' carry no information — only the rough lookback length matters."]
    if imp is not None:
        L += ["", "## What the random forest paid attention to (latest model)", "",
              "| Feature | Importance |", "|---|---|"]
        for k, v in imp.sort_values(ascending=False).head(15).items():
            L.append(f"| {k} | {v:.3f} |")
        L += ["", "Compare 'Gradient boosting' with 'Gradient boosting (basic features only)' in the "
              "ranking: if adding Fourier/Gaussian/Laplacian/Fibonacci/Hurst features doesn't raise "
              "the out-of-sample result, they aren't adding real information."]
    L += ["", "## Read this before acting on the ranking", "",
          f"- {len(R)} ideas were tested. Even if none had any edge, the best of them would look "
          "good by chance. Treat anything that doesn't clearly beat the 'luck' line with suspicion.",
          "- Prefer ideas that are positive in **both** halves and beat both yardsticks.",
          "- Survivorship bias: the stock list is today's large caps, which flatters every "
          "long-only strategy (and buy-and-hold) a little.",
          "- To switch the live bot to a winning idea, ask for it to be wired in; the weekly "
          "backtest will then keep checking it.",
          f"- Run time {secs / 60:.0f} min."]
    txt = "\n".join(L)
    with open(os.path.join(HERE, "lab_report.md"), "w") as f:
        f.write(txt)
    return txt


def telegram_text(R, luck, n_cagr, yrs):
    lines = ["🔬 <b>Strategy lab</b> (unseen period, "
             f"{yrs:.1f}y)", f"NIFTY buy-and-hold: {n_cagr}%/yr · luck line: {luck['p95']:.1f}%/yr", ""]
    body = R[~R["group"].eq("control")].head(8)
    for i, r in enumerate(body.itertuples(index=False), 1):
        mark = "✅" if (r.beats_luck and r.beats_nifty) else ("🟡" if r.beats_luck else "❌")
        lines.append(f"{i}. {mark} {r.name}: {r.cagr_pct}%/yr, win {r.win_rate_pct}%")
    base = R[R["group"].eq("baseline")]
    if len(base):
        b = base.iloc[0]
        lines += ["", f"Your current bot: {b['cagr_pct']}%/yr"]
    lines += ["", "✅ beats luck and Nifty · 🟡 beats luck only · ❌ neither",
              "Full table: lab_report.md in your repo."]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
