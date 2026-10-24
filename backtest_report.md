# Backtest report — 24 Oct 2026

**Decision:** Self-tuned rules adopted: beat defaults on unseen data (edge 0.064%/day vs 0.050%/day; typical capital ₹49,870 vs ₹43,959).

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 161 | 46.6% | 0.864% | 7.0% / -4.49% | 13.5d | 0.064% | 1.36 |
| Default | 145 | 44.1% | 0.562% | 5.99% / -3.73% | 11.2d | 0.0501% | 1.27 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.7 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹49,870 | ₹42,966 | 6.1% | 27.2% | 33.1% | 164 |
| Default | ₹40,000 → ₹43,959 | ₹38,102 | 2.8% | 15.5% | 20.5% | 157 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 252 | 39.3% | 0.226% | 0.0227% | 1.09 |
| without market-regime filter | 447 | 40.9% | 0.561% | 0.0601% | 1.23 |
| without relative-strength filter | 262 | 34.7% | -0.397% | -0.0426% | 0.85 |
| without trailing stop | 252 | 39.3% | 0.226% | 0.0227% | 1.09 |
| without sector cap (3 per sector allowed) | 261 | 38.7% | 0.069% | 0.0072% | 1.03 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ✅ edge/day beats defaults by 10%+
- ✅ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0914%
- Edge per day in the unseen windows right after: 0.0308%
- Retention: 34% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
- Parameter changes between folds: 3 of 7 (frequent flipping = unstable, less trustworthy)

## Live parameters now in use

```json
{
  "min_score": 60,
  "rsi_low": 45,
  "rsi_high": 65,
  "vol_mult": 1.2,
  "near_high_pct": 0.97,
  "stop_atr": 2.0,
  "target_atr": 4.0,
  "trail_atr": 0.0,
  "max_hold_days": 22,
  "regime_filter": 0,
  "rs_filter": 0,
  "rs_lookback": 63
}
```

## Fold by fold

| Train | Test | Chosen params | Train edge/day | Test trades | Test avg/trade | Test win | Test edge/day | Default test edge/day |
|---|---|---|---|---|---|---|---|---|
| 2021-01..2023-01 | 2023-01..2023-07 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=0 | 0.0867% | 25 | 0.504% | 48.0% | 0.0342% | 0.2255% |
| 2021-07..2023-07 | 2023-07..2024-01 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0408% | 31 | 4.437% | 67.7% | 0.3648% | 0.024% |
| 2022-01..2024-01 | 2024-01..2024-07 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.1032% | 24 | 0.648% | 45.8% | 0.0447% | 0.0056% |
| 2022-07..2024-07 | 2024-07..2025-01 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.1155% | 28 | -0.779% | 35.7% | -0.0578% | -0.1117% |
| 2023-01..2025-01 | 2025-01..2025-07 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1384% | 11 | 1.669% | 54.5% | 0.0896% | 0.0978% |
| 2023-07..2025-07 | 2025-07..2026-01 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1151% | 24 | -0.139% | 41.7% | -0.0133% | 0.068% |
| 2024-01..2026-01 | 2026-01..2026-07 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0872% | 9 | -4.355% | 11.1% | -0.3563% | 0.1246% |
| 2024-07..2026-07 | 2026-07..2026-10 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0443% | 9 | 2.152% | 44.4% | 0.1403% | -0.0277% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Dec 2022: 931 trades, win 38.5%, avg hold 42.7 days  
Edge vs NIFTY: +1.27%/month held (1st half +5.51%, 2nd half +0.09% per trade)  
₹40,000 → ₹73,761 typical (bad luck ₹58,965), max drawdown 13.4% · NIFTY 5.9%/yr  
✅ still holding up
