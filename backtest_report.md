# Backtest report — 26 Sep 2026

**Decision:** Self-tuned rules adopted: beat defaults on unseen data (edge 0.051%/day vs 0.034%/day; typical capital ₹49,159 vs ₹47,624).

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 189 | 39.7% | 0.57% | 7.02% / -3.67% | 11.2d | 0.0509% | 1.26 |
| Default | 161 | 42.2% | 0.351% | 5.96% / -3.75% | 10.2d | 0.0343% | 1.16 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.7 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹49,159 | ₹41,241 | 5.7% | 28.7% | 36.5% | 190 |
| Default | ₹40,000 → ₹47,624 | ₹41,937 | 4.8% | 14.2% | 20.4% | 160 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 268 | 39.9% | 0.268% | 0.0278% | 1.11 |
| without market-regime filter | 427 | 43.3% | 0.655% | 0.0667% | 1.27 |
| without relative-strength filter | 272 | 36.4% | -0.232% | -0.0251% | 0.91 |
| without trailing stop | 268 | 39.9% | 0.268% | 0.0278% | 1.11 |
| without sector cap (3 per sector allowed) | 275 | 38.2% | 0.023% | 0.0024% | 1.01 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ✅ edge/day beats defaults by 10%+
- ✅ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.1147%
- Edge per day in the unseen windows right after: 0.0101%
- Retention: 9% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
- Parameter changes between folds: 2 of 7 (frequent flipping = unstable, less trustworthy)

## Live parameters now in use

```json
{
  "min_score": 70,
  "rsi_low": 45,
  "rsi_high": 65,
  "vol_mult": 1.2,
  "near_high_pct": 0.97,
  "stop_atr": 2.0,
  "target_atr": 4.0,
  "trail_atr": 0.0,
  "max_hold_days": 22,
  "regime_filter": 0,
  "rs_filter": 1,
  "rs_lookback": 63
}
```

## Fold by fold

| Train | Test | Chosen params | Train edge/day | Test trades | Test avg/trade | Test win | Test edge/day | Default test edge/day |
|---|---|---|---|---|---|---|---|---|
| 2020-12..2022-12 | 2022-12..2023-06 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0791% | 32 | 1.536% | 46.9% | 0.1314% | 0.1106% |
| 2021-06..2023-06 | 2023-06..2023-12 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1003% | 35 | 2.005% | 48.6% | 0.1938% | -0.0425% |
| 2021-12..2023-12 | 2023-12..2024-06 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1594% | 29 | 2.666% | 51.7% | 0.2135% | 0.0627% |
| 2022-06..2024-06 | 2024-06..2024-12 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1449% | 32 | -1.842% | 21.9% | -0.1669% | 0.0029% |
| 2022-12..2024-12 | 2024-12..2025-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1866% | 9 | 0.524% | 55.6% | 0.0323% | 0.03% |
| 2023-06..2025-06 | 2025-06..2025-12 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.133% | 26 | 0.203% | 34.6% | 0.0184% | 0.1074% |
| 2023-12..2025-12 | 2025-12..2026-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1201% | 9 | -1.931% | 33.3% | -0.1721% | -0.0764% |
| 2024-06..2026-06 | 2026-06..2026-09 | min_score=60, stop_atr=1.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | -0.0057% | 17 | -1.325% | 23.5% | -0.1694% | 0.0235% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.