"""
Diagnostic: which data sources actually work from wherever this is running?

    python3 check_sources.py

Run it once after setup (locally, and via the "Check data sources" workflow
on GitHub) -- the answer can differ between your phone and GitHub's US
servers, especially for NSE, which sometimes blocks foreign/datacentre IPs.
"""

import time

import sources
from universe import NIFTY_UNIVERSE

SAMPLE = NIFTY_UNIVERSE[:5]


def timed(label, fn):
    t0 = time.time()
    try:
        res = fn()
    except Exception as e:
        print(f"❌ {label}: error -- {e}")
        return None
    dt = time.time() - t0
    return res, dt


def main():
    print("Checking data sources...\n")

    r = timed("Yahoo", lambda: sources.yahoo_history(SAMPLE, period="1mo"))
    if r:
        res, dt = r
        if res:
            t = list(res)[0]
            print(f"✅ Yahoo daily: {len(res)}/{len(SAMPLE)} stocks in {dt:.1f}s "
                  f"(latest {t} close ₹{res[t]['Close'].iloc[-1]:.2f} on {res[t].index[-1].date()})")
        else:
            print(f"❌ Yahoo daily: no data returned ({dt:.1f}s)")

    r = timed("Yahoo index", lambda: sources.yahoo_history(["^NSEI"], period="1mo"))
    if r:
        res, dt = r
        print(f"{'✅' if res else '❌'} Yahoo NIFTY index: "
              f"{'ok' if res else 'no data'} ({dt:.1f}s)")

    r = timed("NSE bhavcopy", sources.nse_bhavcopy)
    if r:
        res, dt = r
        if res is not None and not res.empty:
            print(f"✅ NSE official bhavcopy: {len(res)} stocks for "
                  f"{res.attrs.get('trade_date')} in {dt:.1f}s -- cross-checking is ON")
        else:
            print(f"⚠️  NSE official bhavcopy: unreachable ({dt:.1f}s). "
                  "Normal on non-Indian servers; the bot runs on Yahoo alone and "
                  "simply skips the official cross-check.")

    r = timed("Stooq", lambda: sources.stooq_history(SAMPLE[:2]))
    if r:
        res, dt = r
        print(f"{'✅' if res else '⚠️ '} Stooq fallback: {len(res) if res else 0}/2 stocks "
              f"({dt:.1f}s){'' if res else ' -- fallback unavailable, Yahoo-only'}")

    print("\nRule of thumb: Yahoo working = the bot works. NSE and Stooq are "
          "extras (verification and backup).")


if __name__ == "__main__":
    main()
