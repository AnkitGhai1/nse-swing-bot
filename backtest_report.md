# Backtest report — 17 Oct 2026

**Decision:** Kept default rules — tuned rules did NOT pass: edge/day beats defaults by 10%+.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 170 | 39.4% | 0.213% | 6.87% / -4.12% | 12.5d | 0.0171% | 1.09 |
| Default | 157 | 43.9% | 0.481% | 5.83% / -3.71% | 10.6d | 0.0453% | 1.23 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.8 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹47,279 | ₹40,828 | 4.5% | 29.7% | 35.3% | 169 |
| Default | ₹40,000 → ₹44,573 | ₹40,186 | 3.2% | 15.5% | 21.6% | 158 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 262 | 40.5% | 0.24% | 0.0244% | 1.1 |
| without market-regime filter | 439 | 39.9% | 0.137% | 0.0144% | 1.05 |
| without relative-strength filter | 273 | 33.0% | -0.628% | -0.0688% | 0.78 |
| without trailing stop | 262 | 40.5% | 0.24% | 0.0244% | 1.1 |
| without sector cap (3 per sector allowed) | 268 | 38.8% | -0.035% | -0.0037% | 0.99 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ✅ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.059%
- Edge per day in the unseen windows right after: -0.0191%
- Retention: -32% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
- Parameter changes between folds: 3 of 7 (frequent flipping = unstable, less trustworthy)

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
| 2021-01..2023-01 | 2023-01..2023-07 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | -0.0425% | 21 | 1.662% | 57.1% | 0.0981% | 0.116% |
| 2021-07..2023-07 | 2023-07..2024-01 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | -0.0582% | 32 | 2.18% | 53.1% | 0.1865% | 0.1105% |
| 2022-01..2024-01 | 2024-01..2024-07 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1325% | 28 | 2.08% | 50.0% | 0.1683% | 0.0341% |
| 2022-07..2024-07 | 2024-07..2025-01 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1554% | 38 | -1.721% | 23.7% | -0.1858% | -0.0485% |
| 2023-01..2025-01 | 2025-01..2025-07 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.129% | 11 | 1.669% | 54.5% | 0.0896% | 0.1053% |
| 2023-07..2025-07 | 2025-07..2026-01 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0776% | 20 | -2.309% | 20.0% | -0.1932% | 0.0233% |
| 2024-01..2026-01 | 2026-01..2026-07 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0431% | 10 | -2.506% | 30.0% | -0.261% | -0.3299% |
| 2024-07..2026-07 | 2026-07..2026-10 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0352% | 10 | -0.845% | 20.0% | -0.0556% | 0.1503% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Dec 2022: 913 trades, win 38.4%, avg hold 42.5 days  
Edge vs NIFTY: +1.25%/month held (1st half +5.39%, 2nd half -0.01% per trade)  
₹40,000 → ₹72,322 typical (bad luck ₹61,375), max drawdown 14.0% · NIFTY 6.1%/yr  
⚠️ edge has weakened — keep it on paper
