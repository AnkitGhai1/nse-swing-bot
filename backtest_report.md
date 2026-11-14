# Backtest report — 14 Nov 2026

**Decision:** Kept default rules — tuned rules did NOT pass: edge/day beats defaults by 10%+, capital simulation agrees.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 204 | 39.2% | 0.442% | 6.89% / -3.72% | 11.9d | 0.0372% | 1.2 |
| Default | 160 | 41.2% | 0.365% | 6.0% / -3.59% | 10.1d | 0.0361% | 1.17 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.7 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹44,468 | ₹34,316 | 2.9% | 36.4% | 45.3% | 210 |
| Default | ₹40,000 → ₹45,330 | ₹40,189 | 3.7% | 14.4% | 18.4% | 155 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 255 | 37.6% | 0.002% | 0.0002% | 1.0 |
| without market-regime filter | 448 | 38.8% | 0.137% | 0.0147% | 1.05 |
| without relative-strength filter | 260 | 39.2% | -0.102% | -0.0111% | 0.96 |
| without trailing stop | 255 | 37.6% | 0.002% | 0.0002% | 1.0 |
| without sector cap (3 per sector allowed) | 257 | 37.7% | -0.208% | -0.0215% | 0.92 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ❌ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0804%
- Edge per day in the unseen windows right after: -0.002%
- Retention: -2% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
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
| 2021-02..2023-02 | 2023-02..2023-08 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=0 | 0.1016% | 22 | 1.854% | 59.1% | 0.1093% | 0.1558% |
| 2021-08..2023-08 | 2023-08..2024-02 | min_score=70, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=0 | 0.0695% | 36 | 2.495% | 55.6% | 0.2339% | 0.0392% |
| 2022-02..2024-02 | 2024-02..2024-08 | min_score=60, stop_atr=1.5, target_atr=3.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0926% | 33 | 1.279% | 45.5% | 0.1085% | -0.0532% |
| 2022-08..2024-08 | 2024-08..2025-02 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0552% | 36 | -0.429% | 27.8% | -0.042% | -0.1829% |
| 2023-02..2025-02 | 2025-02..2025-08 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1373% | 14 | -0.031% | 42.9% | -0.002% | 0.1315% |
| 2023-08..2025-08 | 2025-08..2026-02 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0692% | 17 | -1.337% | 29.4% | -0.1033% | 0.0099% |
| 2024-02..2026-02 | 2026-02..2026-08 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0671% | 27 | 0.206% | 33.3% | 0.0168% | 0.1787% |
| 2024-08..2026-08 | 2026-08..2026-11 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0508% | 19 | -2.606% | 10.5% | -0.3368% | -0.1721% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Jan 2023: 972 trades, win 38.1%, avg hold 42.5 days  
Edge vs NIFTY: +1.25%/month held (1st half +5.26%, 2nd half +0.23% per trade)  
₹40,000 → ₹73,040 typical (bad luck ₹59,145), max drawdown 13.4% · NIFTY 9.3%/yr  
✅ still holding up
