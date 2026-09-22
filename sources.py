"""
Price data sources, in priority order, with automatic fallback.

1. YAHOO (yfinance) -- free, no key, gives years of daily history plus a live
   in-progress candle during market hours. Primary source.
2. NSE official bhavcopy -- the exchange's OWN end-of-day file, published
   free on nseindia.com. One file contains every stock's OHLCV for that day.
   Used to VERIFY Yahoo's latest close and to patch a missing/stale day.
   It only covers one day per file, so it can't cheaply rebuild years of
   history -- that's why it verifies rather than replaces.
   NOTE: NSE sometimes blocks non-Indian / datacentre IP addresses, so this
   may fail on GitHub's US servers. Run check_sources.py to find out; the
   bot simply skips verification if it's unreachable.
3. STOOQ -- free CSV, no key. Backup for daily history if Yahoo breaks.
   Coverage of Indian stocks is patchy; check_sources.py tells you.

About TradingView: it has no free public API, and scraping their charts
breaks their terms of service, so this bot does not use it. Everything here
is either an official exchange file or a provider's public data endpoint.
"""

import io
import time
import zipfile
from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

NSE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/all-reports",
}
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


# --------------------------------------------------------------------------- #
# 1. Yahoo
# --------------------------------------------------------------------------- #
def yahoo_history(tickers: List[str], period: str = "9mo", interval: str = "1d",
                  batch_size: int = 20, retries: int = 2) -> Dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        data = None
        for attempt in range(retries + 1):
            try:
                data = yf.download(batch, period=period, interval=interval, progress=False,
                                   auto_adjust=True, group_by="ticker", threads=True)
                break
            except Exception as e:
                print(f"[yahoo] attempt {attempt + 1} failed: {e}")
                time.sleep(3)
        if data is None or len(data) == 0:
            continue
        for t in batch:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if t not in data.columns.get_level_values(0):
                        continue
                    df = data[t]
                else:
                    df = data
                df = df.dropna(subset=["Close"])
                if not df.empty:
                    out[t] = df[OHLCV]
            except Exception as e:
                print(f"[yahoo] skip {t}: {e}")
    return out


# --------------------------------------------------------------------------- #
# 2. NSE official bhavcopy (one trading day, every stock)
# --------------------------------------------------------------------------- #
def _nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=15)      # picks up cookies
    except Exception:
        pass
    return s


def nse_bhavcopy(day: Optional[date] = None, lookback: int = 5) -> Optional[pd.DataFrame]:
    """Official EOD OHLCV for one trading day, indexed by NSE symbol.
    Walks back up to `lookback` days to skip weekends/holidays.
    Returns None if NSE is unreachable (common from non-Indian servers)."""
    day = day or date.today()
    s = _nse_session()
    for back in range(lookback + 1):
        d = day - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        df = _try_udiff(s, d)
        if df is None:
            df = _try_sec_bhavdata(s, d)
        if df is not None and not df.empty:
            df.attrs["trade_date"] = d
            return df
    print("[nse] official bhavcopy unreachable (NSE often blocks non-Indian servers) "
          "-- continuing without the cross-check")
    return None


def _try_udiff(s: requests.Session, d: date) -> Optional[pd.DataFrame]:
    """Current (post-July-2024) format: BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip"""
    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    try:
        r = s.get(url, timeout=30)
        if r.status_code != 200 or not r.content[:2] == b"PK":
            return None
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            raw = pd.read_csv(z.open(z.namelist()[0]))
        raw.columns = [c.strip() for c in raw.columns]
        eq = raw[(raw.get("SctySrs") == "EQ")] if "SctySrs" in raw else raw
        out = pd.DataFrame({
            "Open": pd.to_numeric(eq["OpnPric"], errors="coerce"),
            "High": pd.to_numeric(eq["HghPric"], errors="coerce"),
            "Low": pd.to_numeric(eq["LwPric"], errors="coerce"),
            "Close": pd.to_numeric(eq["ClsPric"], errors="coerce"),
            "Volume": pd.to_numeric(eq["TtlTradgVol"], errors="coerce"),
        })
        out.index = eq["TckrSymb"].astype(str).str.strip()
        return out.dropna(subset=["Close"])
    except Exception:
        return None


def _try_sec_bhavdata(s: requests.Session, d: date) -> Optional[pd.DataFrame]:
    """Older-style full security file: sec_bhavdata_full_DDMMYYYY.csv"""
    url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"
    try:
        r = s.get(url, timeout=30)
        if r.status_code != 200 or b"SYMBOL" not in r.content[:200]:
            return None
        raw = pd.read_csv(io.BytesIO(r.content))
        raw.columns = [c.strip() for c in raw.columns]
        eq = raw[raw["SERIES"].astype(str).str.strip() == "EQ"]
        out = pd.DataFrame({
            "Open": pd.to_numeric(eq["OPEN_PRICE"], errors="coerce"),
            "High": pd.to_numeric(eq["HIGH_PRICE"], errors="coerce"),
            "Low": pd.to_numeric(eq["LOW_PRICE"], errors="coerce"),
            "Close": pd.to_numeric(eq["CLOSE_PRICE"], errors="coerce"),
            "Volume": pd.to_numeric(eq["TTL_TRD_QNTY"], errors="coerce"),
        })
        out.index = eq["SYMBOL"].astype(str).str.strip()
        return out.dropna(subset=["Close"])
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# 3. Stooq (fallback daily history)
# --------------------------------------------------------------------------- #
def stooq_history(tickers: List[str], suffix: str = ".in", pause: float = 0.3) -> Dict[str, pd.DataFrame]:
    out = {}
    for t in tickers:
        sym = t.replace(".NS", "").lower() + suffix
        try:
            r = requests.get(f"https://stooq.com/q/d/l/?s={sym}&i=d", timeout=20)
            if r.status_code != 200 or b"Date" not in r.content[:50]:
                continue
            df = pd.read_csv(io.BytesIO(r.content), parse_dates=["Date"]).set_index("Date")
            df = df.rename(columns=str.title)
            if "Close" in df and not df.empty:
                for c in OHLCV:
                    if c not in df:
                        df[c] = df["Close"] if c != "Volume" else 0
                out[t] = df[OHLCV]
        except Exception:
            pass
        time.sleep(pause)
    return out


# --------------------------------------------------------------------------- #
# Cross-checking
# --------------------------------------------------------------------------- #
def cross_check(prices: Dict[str, pd.DataFrame], bhav: pd.DataFrame,
                tol_pct: float = 1.0) -> Dict[str, float]:
    """Compare each stock's latest close against NSE's official close for the
    same day. Returns {ticker: difference%} for anything beyond tolerance --
    those get skipped rather than traded on suspect data."""
    bad = {}
    if bhav is None or bhav.empty:
        return bad
    bhav_day = bhav.attrs.get("trade_date")
    for t, df in prices.items():
        sym = t.replace(".NS", "")
        if sym not in bhav.index or df.empty:
            continue
        if bhav_day and df.index[-1].date() != bhav_day:
            continue                       # different day -> not comparable
        official = float(bhav.loc[sym, "Close"]) if not isinstance(bhav.loc[sym], pd.DataFrame) \
            else float(bhav.loc[sym, "Close"].iloc[0])
        ours = float(df["Close"].iloc[-1])
        if official > 0:
            diff = abs(ours - official) / official * 100
            if diff > tol_pct:
                bad[t] = round(diff, 2)
    return bad
