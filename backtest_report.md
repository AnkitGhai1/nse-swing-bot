# Backtest report — 22 Sep 2026

**Decision:** Kept default rules — self-tuning failed: edge/day beats defaults by 10%+, capital simulation agrees.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 166 | 41.0% | 0.068% | 6.14% / -4.15% | 12.8d | 0.0053% | 1.03 |
| Default | 158 | 39.2% | 0.182% | 6.27% / -3.75% | 10.5d | 0.0172% | 1.08 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.7 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹44,105 | ₹33,543 | 2.6% | 30.9% | 35.7% | 180 |
| Default | ₹40,000 → ₹45,970 | ₹39,783 | 3.8% | 14.2% | 20.2% | 161 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 262 | 38.9% | 0.223% | 0.0223% | 1.09 |
| without market-regime filter | 438 | 40.9% | 0.311% | 0.0324% | 1.12 |
| without relative-strength filter | 294 | 38.4% | -0.117% | -0.0136% | 0.95 |
| without trailing stop | 262 | 38.9% | 0.223% | 0.0223% | 1.09 |
| without sector cap (3 per sector allowed) | 267 | 38.2% | -0.059% | -0.006% | 0.98 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ❌ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0871%
- Edge per day in the unseen windows right after: -0.0047%
- Retention: -5% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
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
| 2020-12..2022-12 | 2022-12..2023-06 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.1054% | 25 | -0.576% | 40.0% | -0.0397% | 0.2582% |
| 2021-06..2023-06 | 2023-06..2023-12 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0294% | 29 | 0.749% | 48.3% | 0.0605% | 0.0206% |
| 2021-12..2023-12 | 2023-12..2024-06 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0904% | 31 | 1.779% | 51.6% | 0.1519% | 0.0112% |
| 2022-06..2024-06 | 2024-06..2024-12 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1208% | 31 | -0.979% | 29.0% | -0.087% | -0.0795% |
| 2022-12..2024-12 | 2024-12..2025-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1421% | 8 | 1.16% | 62.5% | 0.0672% | -0.0602% |
| 2023-06..2025-06 | 2025-06..2025-12 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1205% | 21 | -0.729% | 28.6% | -0.0547% | 0.1105% |
| 2023-12..2025-12 | 2025-12..2026-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0899% | 10 | -2.825% | 30.0% | -0.2278% | -0.2718% |
| 2024-06..2026-06 | 2026-06..2026-09 | min_score=60, stop_atr=1.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | -0.002% | 11 | 1.216% | 45.5% | 0.0917% | 0.0604% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.