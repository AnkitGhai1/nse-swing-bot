# Backtest report — 28 Nov 2026

**Decision:** Kept default rules — tuned rules did NOT pass: profitable after costs, profit factor > 1, edge/day beats defaults by 10%+, capital simulation agrees.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 203 | 36.0% | -0.058% | 7.11% / -4.08% | 11.9d | -0.0049% | 0.98 |
| Default | 156 | 41.0% | 0.029% | 5.64% / -3.88% | 10.4d | 0.0028% | 1.01 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.8 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹36,738 | ₹31,931 | -2.2% | 32.7% | 38.5% | 210 |
| Default | ₹40,000 → ₹45,545 | ₹39,480 | 3.9% | 15.1% | 20.2% | 157 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 253 | 38.3% | -0.156% | -0.016% | 0.94 |
| without market-regime filter | 438 | 39.5% | -0.007% | -0.0008% | 1.0 |
| without relative-strength filter | 266 | 34.2% | -0.508% | -0.0568% | 0.81 |
| without trailing stop | 253 | 38.3% | -0.156% | -0.016% | 0.94 |
| without sector cap (3 per sector allowed) | 259 | 37.5% | -0.216% | -0.0227% | 0.92 |

## Adoption checks

- ✅ enough trades
- ❌ profitable after costs
- ❌ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ❌ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0739%
- Edge per day in the unseen windows right after: -0.0092%
- Retention: -12% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
- Parameter changes between folds: 6 of 7 (frequent flipping = unstable, less trustworthy)

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
| 2021-02..2023-02 | 2023-02..2023-08 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=0 | 0.0958% | 35 | 0.943% | 42.9% | 0.0894% | 0.1327% |
| 2021-08..2023-08 | 2023-08..2024-02 | min_score=60, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.086% | 31 | 0.129% | 38.7% | 0.0109% | -0.0312% |
| 2022-02..2024-02 | 2024-02..2024-08 | min_score=70, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1177% | 31 | -0.269% | 38.7% | -0.0232% | -0.0452% |
| 2022-08..2024-08 | 2024-08..2025-02 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0767% | 32 | -0.928% | 25.0% | -0.0807% | -0.0665% |
| 2023-02..2025-02 | 2025-02..2025-08 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1286% | 14 | -0.031% | 42.9% | -0.002% | 0.0757% |
| 2023-08..2025-08 | 2025-08..2026-02 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.0729% | 19 | 0.261% | 42.1% | 0.0206% | 0.1261% |
| 2024-02..2026-02 | 2026-02..2026-08 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=1 | 0.0022% | 28 | -0.231% | 28.6% | -0.0176% | -0.2773% |
| 2024-08..2026-08 | 2026-08..2026-11 | min_score=60, stop_atr=2.0, target_atr=3.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0116% | 13 | -0.685% | 30.8% | -0.0707% | None% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Jan 2023: 950 trades, win 38.2%, avg hold 42.6 days  
Edge vs NIFTY: +1.27%/month held (1st half +5.26%, 2nd half +0.26% per trade)  
₹40,000 → ₹75,634 typical (bad luck ₹59,941), max drawdown 13.2% · NIFTY 10.3%/yr  
✅ still holding up
