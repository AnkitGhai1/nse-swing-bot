# Backtest report — 31 Oct 2026

**Decision:** Kept default rules — tuned rules did NOT pass: edge/day beats defaults by 10%+, capital simulation agrees.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 183 | 38.3% | 0.254% | 6.78% / -3.79% | 11.6d | 0.0219% | 1.11 |
| Default | 150 | 43.3% | 0.433% | 5.89% / -3.74% | 10.9d | 0.0399% | 1.2 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.7 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹39,112 | ₹32,565 | -0.6% | 25.0% | 32.6% | 184 |
| Default | ₹40,000 → ₹44,019 | ₹36,234 | 2.8% | 15.9% | 20.8% | 156 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 243 | 38.7% | 0.035% | 0.0034% | 1.01 |
| without market-regime filter | 435 | 40.5% | 0.31% | 0.0324% | 1.12 |
| without relative-strength filter | 271 | 38.0% | -0.028% | -0.0031% | 0.99 |
| without trailing stop | 243 | 38.7% | 0.035% | 0.0034% | 1.01 |
| without sector cap (3 per sector allowed) | 243 | 37.4% | -0.146% | -0.0142% | 0.94 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ❌ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.1117%
- Edge per day in the unseen windows right after: -0.0229%
- Retention: -21% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
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
| 2021-01..2023-01 | 2023-01..2023-07 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=0 | 0.1395% | 30 | 0.929% | 46.7% | 0.07% | 0.2064% |
| 2021-07..2023-07 | 2023-07..2024-01 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0951% | 32 | 2.89% | 56.2% | 0.2649% | 0.0283% |
| 2022-01..2024-01 | 2024-01..2024-07 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1663% | 35 | 0.316% | 42.9% | 0.0299% | -0.0106% |
| 2022-07..2024-07 | 2024-07..2025-01 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1489% | 30 | -0.333% | 30.0% | -0.0288% | -0.0935% |
| 2023-01..2025-01 | 2025-01..2025-07 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1373% | 14 | 0.144% | 42.9% | 0.0096% | 0.0813% |
| 2023-07..2025-07 | 2025-07..2026-01 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0987% | 18 | -2.068% | 16.7% | -0.1519% | 0.1079% |
| 2024-01..2026-01 | 2026-01..2026-07 | min_score=50, stop_atr=1.5, target_atr=3.0, trail_atr=3.0, regime_filter=1, rs_filter=1 | 0.1155% | 14 | -0.604% | 35.7% | -0.0929% | -0.1374% |
| 2024-07..2026-07 | 2026-07..2026-10 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | -0.0078% | 10 | -3.124% | 0.0% | -0.284% | -0.029% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Dec 2022: 960 trades, win 38.1%, avg hold 42.5 days  
Edge vs NIFTY: +1.27%/month held (1st half +5.47%, 2nd half +0.22% per trade)  
₹40,000 → ₹72,262 typical (bad luck ₹58,403), max drawdown 13.8% · NIFTY 6.4%/yr  
✅ still holding up
