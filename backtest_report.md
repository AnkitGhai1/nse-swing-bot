# Backtest report — 07 Nov 2026

**Decision:** Self-tuned rules adopted: beat defaults on unseen data (edge 0.050%/day vs -0.002%/day; typical capital ₹49,176 vs ₹44,847).

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 187 | 42.8% | 0.65% | 7.32% / -4.34% | 13.0d | 0.0502% | 1.26 |
| Default | 155 | 38.7% | -0.019% | 6.03% / -3.84% | 10.4d | -0.0018% | 0.99 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.8 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹49,176 | ₹40,340 | 5.7% | 42.1% | 46.7% | 198 |
| Default | ₹40,000 → ₹44,847 | ₹37,712 | 3.4% | 14.8% | 22.4% | 157 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 247 | 35.2% | -0.336% | -0.0339% | 0.88 |
| without market-regime filter | 440 | 40.5% | 0.359% | 0.0377% | 1.15 |
| without relative-strength filter | 264 | 34.8% | -0.472% | -0.0512% | 0.83 |
| without trailing stop | 247 | 35.2% | -0.336% | -0.0339% | 0.88 |
| without sector cap (3 per sector allowed) | 255 | 36.9% | -0.125% | -0.0129% | 0.95 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ✅ edge/day beats defaults by 10%+
- ✅ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0687%
- Edge per day in the unseen windows right after: 0.0287%
- Retention: 42% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
- Parameter changes between folds: 6 of 7 (frequent flipping = unstable, less trustworthy)

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
| 2021-02..2023-02 | 2023-02..2023-08 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0468% | 22 | 1.49% | 63.6% | 0.0856% | 0.2919% |
| 2021-08..2023-08 | 2023-08..2024-02 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0867% | 32 | 2.506% | 50.0% | 0.2215% | -0.0691% |
| 2022-02..2024-02 | 2024-02..2024-08 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | -0.0353% | 25 | 2.213% | 56.0% | 0.1467% | -0.0009% |
| 2022-08..2024-08 | 2024-08..2025-01 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.1147% | 31 | -0.063% | 38.7% | -0.0055% | -0.0828% |
| 2023-02..2025-01 | 2025-01..2025-08 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1519% | 14 | -0.031% | 42.9% | -0.002% | 0.0365% |
| 2023-08..2025-08 | 2025-08..2026-01 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1068% | 18 | -0.417% | 33.3% | -0.0328% | -0.0007% |
| 2024-01..2026-01 | 2026-01..2026-07 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0369% | 34 | -0.56% | 29.4% | -0.0514% | -0.376% |
| 2024-07..2026-07 | 2026-07..2026-11 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0409% | 11 | -1.613% | 18.2% | -0.1324% | 0.0826% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Jan 2023: 965 trades, win 38.1%, avg hold 42.5 days  
Edge vs NIFTY: +1.26%/month held (1st half +5.43%, 2nd half +0.21% per trade)  
₹40,000 → ₹75,695 typical (bad luck ₹61,372), max drawdown 13.4% · NIFTY 9.0%/yr  
✅ still holding up
