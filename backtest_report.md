# Backtest report — 23 Sep 2026

**Decision:** Kept default rules — self-tuning failed: profitable after costs, profit factor > 1, edge/day beats defaults by 10%+, capital simulation agrees.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 189 | 39.7% | -0.142% | 5.95% / -4.15% | 13.0d | -0.0109% | 0.94 |
| Default | 168 | 44.0% | 0.613% | 6.2% / -3.79% | 9.8d | 0.0626% | 1.29 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.7 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹42,254 | ₹34,632 | 1.5% | 28.0% | 34.1% | 205 |
| Default | ₹40,000 → ₹44,471 | ₹39,275 | 2.9% | 14.2% | 21.7% | 161 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 274 | 40.9% | 0.305% | 0.0322% | 1.13 |
| without market-regime filter | 432 | 38.9% | 0.015% | 0.0015% | 1.01 |
| without relative-strength filter | 283 | 35.0% | -0.406% | -0.0457% | 0.85 |
| without trailing stop | 274 | 40.9% | 0.305% | 0.0322% | 1.13 |
| without sector cap (3 per sector allowed) | 276 | 36.6% | -0.125% | -0.0132% | 0.95 |

## Adoption checks

- ✅ enough trades
- ❌ profitable after costs
- ❌ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ❌ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0962%
- Edge per day in the unseen windows right after: -0.0362%
- Retention: -38% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
- Parameter changes between folds: 5 of 7 (frequent flipping = unstable, less trustworthy)

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
| 2020-12..2022-12 | 2022-12..2023-06 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=0 | 0.112% | 23 | -0.979% | 39.1% | -0.0601% | 0.1795% |
| 2021-06..2023-06 | 2023-06..2023-12 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0727% | 27 | 0.012% | 40.7% | 0.0009% | 0.0675% |
| 2021-12..2023-12 | 2023-12..2024-06 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1689% | 35 | 1.724% | 48.6% | 0.1559% | 0.1044% |
| 2022-06..2024-06 | 2024-06..2024-12 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1726% | 32 | -0.201% | 34.4% | -0.0192% | -0.1% |
| 2022-12..2024-12 | 2024-12..2025-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0784% | 29 | -0.618% | 41.4% | -0.0438% | 0.0106% |
| 2023-06..2025-06 | 2025-06..2025-12 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0998% | 26 | -0.336% | 38.5% | -0.0237% | 0.1162% |
| 2023-12..2025-12 | 2025-12..2026-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.082% | 9 | -3.113% | 22.2% | -0.2668% | 0.0339% |
| 2024-06..2026-06 | 2026-06..2026-09 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | -0.0168% | 8 | -0.484% | 37.5% | -0.0331% | 0.0235% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.