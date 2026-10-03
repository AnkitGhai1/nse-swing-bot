# Backtest report — 03 Oct 2026

**Decision:** Kept default rules — tuned rules did NOT pass: edge/day beats defaults by 10%+, capital simulation agrees.

**Edge check:** passed (profitable on unseen data after costs).

History: ~6 years, 8 walk-forward folds (train on 2 years → test on the next 6 months the tuner never saw, then slide forward). Everything below is from the unseen test periods only.

## Trades you would actually have taken (unseen data, after 0.30% costs)

| Rules | Trades | Win rate | Avg/trade | Avg win / loss | Avg hold | Edge per day | Profit factor |
|---|---|---|---|---|---|---|---|
| Self-tuned | 194 | 37.6% | 0.133% | 6.36% / -3.62% | 10.7d | 0.0124% | 1.06 |
| Default | 155 | 44.5% | 0.4% | 5.62% / -3.79% | 10.7d | 0.0374% | 1.19 |

## Your capital, simulated (3 slots, live sizing rules, compounding, 3.7 years)

Median of 60 simulations with shuffled tie-breaks, plus the worst 10%.

| Rules | Typical result | Bad-luck result | CAGR | Max drawdown | Bad-luck drawdown | Trades taken |
|---|---|---|---|---|---|---|
| Self-tuned | ₹40,000 → ₹43,265 | ₹35,219 | 2.1% | 32.0% | 39.3% | 195 |
| Default | ₹40,000 → ₹49,951 | ₹43,103 | 6.7% | 13.5% | 19.9% | 157 |

## Do the upgrades help? (whole history, trades actually taken)

One switch changed at a time, everything else at defaults. Not walk-forward,
so read it as a sanity check, not proof.

| Variant | Trades | Win rate | Avg/trade | Edge per day | Profit factor |
|---|---|---|---|---|---|
| Default rules (all upgrades on) | 254 | 39.4% | -0.05% | -0.0049% | 0.98 |
| without market-regime filter | 432 | 41.9% | 0.497% | 0.0511% | 1.21 |
| without relative-strength filter | 276 | 39.1% | -0.03% | -0.0033% | 0.99 |
| without trailing stop | 254 | 39.4% | -0.05% | -0.0049% | 0.98 |
| without sector cap (3 per sector allowed) | 265 | 40.4% | 0.033% | 0.0033% | 1.01 |

## Adoption checks

- ✅ enough trades
- ✅ profitable after costs
- ✅ profit factor > 1
- ❌ edge/day beats defaults by 10%+
- ❌ capital simulation agrees

## Overfitting check

- Edge per day in training windows: 0.0971%
- Edge per day in the unseen windows right after: -0.0491%
- Retention: -51% (70%+ is healthy; under ~40% means the tuner is mostly fitting noise)
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
| 2020-12..2022-12 | 2022-12..2023-06 | min_score=70, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=0 | 0.0693% | 27 | 0.554% | 44.4% | 0.0445% | 0.1264% |
| 2021-06..2023-06 | 2023-06..2023-12 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.0966% | 38 | 1.104% | 39.5% | 0.1195% | 0.0484% |
| 2021-12..2023-12 | 2023-12..2024-06 | min_score=60, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.123% | 32 | 2.391% | 53.1% | 0.2024% | 0.0063% |
| 2022-06..2024-06 | 2024-06..2024-12 | min_score=50, stop_atr=1.5, target_atr=4.0, trail_atr=3.0, regime_filter=0, rs_filter=1 | 0.1168% | 33 | -1.27% | 27.3% | -0.1201% | -0.1062% |
| 2022-12..2024-12 | 2024-12..2025-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=3.0, regime_filter=1, rs_filter=1 | 0.1078% | 13 | -2.243% | 30.8% | -0.1585% | -0.1103% |
| 2023-06..2025-06 | 2025-06..2025-12 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.1186% | 22 | 1.241% | 50.0% | 0.1062% | 0.2401% |
| 2023-12..2025-12 | 2025-12..2026-06 | min_score=50, stop_atr=2.0, target_atr=4.0, trail_atr=0.0, regime_filter=1, rs_filter=1 | 0.113% | 9 | -3.213% | 22.2% | -0.3178% | -0.0903% |
| 2024-06..2026-06 | 2026-06..2026-10 | min_score=60, stop_atr=1.0, target_atr=4.0, trail_atr=0.0, regime_filter=0, rs_filter=0 | 0.0314% | 20 | -1.749% | 15.0% | -0.2691% | 0.048% |

## Caveats
- Survivorship bias: the stock list is today's large caps, which by definition survived. Real past results would have been somewhat worse.
- Fills assume you buy at the next open and your stop/target orders fill at their price; slippage on fast days can be worse.
- Past performance does not guarantee future results.

## Trend track (paper): 20/50 moving-average crossover

📈 **Trend track (20/50 crossover)** on unseen data since Dec 2022: 904 trades, win 38.6%, avg hold 42.5 days  
Edge vs NIFTY: +1.26%/month held (1st half +5.35%, 2nd half -0.05% per trade)  
₹40,000 → ₹71,717 typical (bad luck ₹58,327), max drawdown 12.7% · NIFTY 4.9%/yr  
⚠️ edge has weakened — keep it on paper
