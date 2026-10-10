# Backtest report — 10 Oct 2026

**Decision:** Kept default rules — tuned rules did NOT pass: edge/day beats defaults by 10%+, capital simulation agrees.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 151 | 42.4% | 0.373% | 6.4% / -4.06% | 13.7d | 0.0272% | 1.16 |
| Default | 160 | 41.9% | 0.377% | 5.91% / -3.61% | 10.1d | 0.0373% | 1.18 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.8 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹41,636 | ₹34,175 | 1.1% | 26.4% | 33.4% | 163 |
| Default | ₹40,000 → ₹44,535 | ₹37,806 | 3.2% | 15.4% | 22.1% | 156 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 266 | 41.0% | 0.271% | 0.0284% | 1.12 |
| without market-regime filter | 451 | 39.2% | 0.19% | 0.0205% | 1.07 |
| without relative-strength filter | 265 | 35.5% | -0.431% | -0.0456% | 0.84 |
| without trailing stop | 266 | 41.0% | 0.271% | 0.0284% | 1.12 |
| without sector cap (3 per sector allowed) | 271 | 38.7% | 0.045% | 0.0048% | 1.02 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ❌ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0519%
- Edge per day in the unseen windows right after: -0.0274%
- Retention: -53% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
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
| 2021-01..2023-01 | 2023-01..2023-07 | min_score=70, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0184% | 25 | 1.508% | 48.0% | 0.1099% | 0.1767% |
| 2021-07..2023-07 | 2023-07..2024-01 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0122% | 29 | 1.222% | 48.3% | 0.0913% | 0.0377% |
| 2022-01..2024-01 | 2024-01..2024-07 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0031% | 23 | 2.418% | 56.5% | 0.1665% | 0.1015% |
| 2022-07..2024-07 | 2024-07..2025-01 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0691% | 23 | -1.052% | 34.8% | -0.0671% | -0.1049% |
| 2023-01..2025-01 | 2025-01..2025-07 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1443% | 13 | 0.694% | 46.2% | 0.0422% | 0.0844% |
| 2023-07..2025-07 | 2025-07..2026-01 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.107% | 20 | -0.903% | 35.0% | -0.082% | 0.0363% |
| 2024-01..2026-01 | 2026-01..2026-07 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0575% | 9 | -3.048% | 22.2% | -0.3976% | -0.307% |
| 2024-07..2026-07 | 2026-07..2026-10 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0036% | 9 | -1.305% | 22.2% | -0.0827% | -0.0528% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Dec 2022: 906 trades, win 38.5%, avg hold 42.5 days  
Edge vs NIFTY: +1.27%/month held (1st half +5.34%, 2nd half +0.03% per trade)  
₹40,000 → ₹68,792 typical (bad luck ₹58,140), max drawdown 14.9% · NIFTY 5.1%/yr  
✅ still holding up
