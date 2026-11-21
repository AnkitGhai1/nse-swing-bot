# Backtest report — 21 Nov 2026

**Decision:** Kept default rules — tuned rules did NOT pass: edge/day beats defaults by 10%+.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 195 | 43.6% | 0.201% | 6.5% / -4.67% | 13.5d | 0.0149% | 1.08 |
| Default | 153 | 40.5% | 0.299% | 6.21% / -3.73% | 10.6d | 0.0283% | 1.13 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.8 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹45,840 | ₹37,462 | 3.7% | 35.0% | 44.1% | 211 |
| Default | ₹40,000 → ₹44,174 | ₹37,093 | 2.9% | 14.9% | 20.6% | 155 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 253 | 37.2% | -0.073% | -0.0075% | 0.97 |
| without market-regime filter | 446 | 38.8% | 0.005% | 0.0006% | 1.0 |
| without relative-strength filter | 264 | 33.3% | -0.693% | -0.0765% | 0.75 |
| without trailing stop | 253 | 37.2% | -0.073% | -0.0075% | 0.97 |
| without sector cap (3 per sector allowed) | 255 | 36.1% | -0.2% | -0.0207% | 0.92 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ✅ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0694%
- Edge per day in the unseen windows right after: 0.0086%
- Retention: 12% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
- Parameter changes between folds: 4 of 7 (frequent flipping = unstable, less trustworthy)

## Live parameters now in use

```json
{
  "min_score": 60,
  "rsi_low": 45,
  "rsi_high": 65,
  "vol_mult": 1.2,
  "near_high_pct": 0.97,
  "stop_atr": 1.5,
  "target_atr": 3.0,
  "trail_atr": 0.0,
  "max_hold_days": 22,
  "regime_filter": 1,
  "rs_filter": 1,
  "rs_lookback": 63
}
```

## Fold by fold

| Train | Test | Chosen params | Train edge/day | Test trades | Test avg/trade | Test win | Test edge/day | Default test edge/day |
|---|---|---|---|---|---|---|---|---|
| 2021-02..2023-02 | 2023-02..2023-08 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0617% | 22 | 2.99% | 72.7% | 0.1788% | 0.1846% |
| 2021-08..2023-08 | 2023-08..2024-02 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0624% | 28 | 4.099% | 67.9% | 0.3171% | 0.008% |
| 2022-02..2024-02 | 2024-02..2024-08 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.078% | 24 | -1.705% | 29.2% | -0.1163% | -0.013% |
| 2022-08..2024-08 | 2024-08..2025-02 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0954% | 30 | -1.4% | 33.3% | -0.119% | -0.0957% |
| 2023-02..2025-02 | 2025-02..2025-08 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.1094% | 23 | -0.49% | 52.2% | -0.0299% | 0.0142% |
| 2023-08..2025-08 | 2025-08..2026-02 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0667% | 26 | -0.476% | 34.6% | -0.0337% | 0.0424% |
| 2024-02..2026-02 | 2026-02..2026-08 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0342% | 31 | -0.994% | 29.0% | -0.0877% | -0.0393% |
| 2024-08..2026-08 | 2026-08..2026-11 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0474% | 11 | -0.369% | 27.3% | -0.0406% | None% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Jan 2023: 969 trades, win 38.1%, avg hold 42.4 days  
Edge vs NIFTY: +1.24%/month held (1st half +5.11%, 2nd half +0.27% per trade)  
₹40,000 → ₹67,145 typical (bad luck ₹55,153), max drawdown 12.8% · NIFTY 9.7%/yr  
✅ still holding up
