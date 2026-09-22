"""
The one function the rest of the bot calls for prices: download().

It tries Yahoo first, falls back to Stooq if Yahoo returns nothing, caches
results for the run, and (for end-of-day use) can verify the latest close
against NSE's official bhavcopy.
"""

from typing import Dict, List, Optional

import pandas as pd

import sources

_cache: Dict[tuple, Dict[str, pd.DataFrame]] = {}
INDEX_TICKER = "^NSEI"          # NIFTY 50, used for the market-regime filter


def download(tickers: List[str], period: str = "9mo", interval: str = "1d",
             use_cache: bool = True, **kw) -> Dict[str, pd.DataFrame]:
    key = (tuple(sorted(tickers)), period, interval)
    if use_cache and key in _cache:
        return _cache[key]

    out = sources.yahoo_history(tickers, period=period, interval=interval)
    missing = [t for t in tickers if t not in out]
    if len(missing) > len(tickers) * 0.5 and interval == "1d":
        print(f"[data] Yahoo returned only {len(out)}/{len(tickers)} -- trying Stooq for the rest")
        out.update(sources.stooq_history(missing))

    if use_cache:
        _cache[key] = out
    return out


def index_history(period: str = "9mo") -> Optional[pd.DataFrame]:
    """NIFTY 50 history for the market-regime and relative-strength filters."""
    d = download([INDEX_TICKER], period=period, interval="1d")
    return d.get(INDEX_TICKER)


def verify_against_nse(prices: Dict[str, pd.DataFrame], tol_pct: float = 1.0):
    """Returns (suspect_tickers, status_text). Silently returns nothing
    suspect if NSE can't be reached (common from non-Indian servers)."""
    bhav = sources.nse_bhavcopy()
    if bhav is None or bhav.empty:
        return set(), "NSE cross-check unavailable (site unreachable from this server)"
    bad = sources.cross_check(prices, bhav, tol_pct=tol_pct)
    if bad:
        detail = ", ".join(f"{t.replace('.NS', '')} {d}%" for t, d in list(bad.items())[:5])
        return set(bad), f"NSE cross-check: {len(bad)} price mismatch(es) skipped ({detail})"
    return set(), f"NSE cross-check: OK for {len(prices)} stocks"
