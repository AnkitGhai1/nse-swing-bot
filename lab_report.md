# Strategy lab — 2026-09-29

109 NSE stocks, scored on **Oct 2021 – Sep 2026** (4.9 years; 1st half = Oct 2021–Apr 2024, 2nd half = Apr 2024–Sep 2026). ₹40,000 capital, 2% risk per trade, 0.30% costs per trade, entries at the next morning's open.

## How to read this

- **Edge / month** = how much a trade earns *above NIFTY over the same days*, after costs, scaled to one month (21 trading days) of money tied up. 0 = no better than holding the index. This uses every signal, so it hardly depends on luck with slots.
- **Worst case** = the edge's lower 90% confidence bound. Trades that overlap in time move together, so this is measured on monthly averages to avoid over-confidence. **The ranking is by this number.**
- **1st / 2nd half** = market-beating return per trade in each half. Both must be positive.
- **10-slot growth** = yearly growth in a research simulation with 10 slots (much less luck than with 3). **3-slot growth** = what your real settings would have made — noisy, shown for reference only.

**Verdict:** ✅ = beats luck, positive in both halves, worst case above 0, and 10-slot growth beats both NIFTY and the luck line · 🟡 = beats luck and positive in both halves, but not confidently · ❌ = fails at least one of those.

## Yardsticks

- **NIFTY 50 buy-and-hold:** 5.0% a year (worst fall 16.5%).
- **Luck** (40 random-entry runs): edge median 0.09%, 95th percentile **0.43%/month**; 10-slot growth median 2.4%, 95th percentile **10.8%/yr**; 3-slot growth ranged up to 13.5%/yr by pure chance.

## Ranking (by worst-case market-beating edge)

| # | Verdict | Strategy | Type | Trades | Win % | Hold (days) | Edge / month | Worst case | 1st half | 2nd half | 10-slot growth | 3-slot growth | Worst fall (10-slot) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 🟡 | SMA crossover — Random numbers lookbacks (26/84, 10/33, 32/87, 5/91) | numbers | 1226 | 34.0 | 43.1 | +0.83% (0.73..0.91) | +0.25% | +2.9% | +0.27% | 8.4% | 15.3% | 17.7% |
| 2 | 🟡 | SMA crossover — Round lookbacks (10/25, 15/35, 20/50, 30/90) | numbers | 1572 | 35.5 | 36.8 | +0.83% (0.73..0.98) | +0.21% | +2.52% | +0.16% | 8.6% | 9.5% | 15.8% |
| 3 | ❌ | Turtle 55-day breakout | popular | 1261 | 31.6 | 30.5 | +0.61% | +0.11% | +1.77% | -0.17% | 9.4% | 5.5% | 15.0% |
| 4 | 🟡 | SMA crossover — Prime lookbacks (7/23, 11/37, 19/53, 31/89) | numbers | 1668 | 36.0 | 36.7 | +0.82% (0.46..1.12) | -0.01% | +2.48% | +0.29% | 8.5% | 6.0% | 18.2% |
| 5 | ❌ | Supertrend(10,3) flip | popular | 1716 | 37.6 | 34.1 | +0.38% | -0.07% | +1.47% | -0.28% | 6.3% | 3.8% | 18.8% |
| 6 | 🟡 | SMA crossover — Fibonacci lookbacks (8/21, 13/34, 21/55, 34/89) | numbers | 1706 | 35.9 | 36.5 | +0.75% (0.38..0.99) | -0.08% | +2.33% | +0.28% | 9.5% | 0.8% | 18.1% |
| 7 | ❌ | Fourier cycle turn | natural | 1932 | 41.8 | 13.8 | +0.34% | -0.19% | +0.69% | -0.33% | 4.8% | 12.6% | 18.4% |
| 8 | ❌ | 12-1 momentum rotation (monthly) | popular | 1644 | 49.6 | 17.7 | +0.28% | -0.36% | +0.77% | -0.42% | 1.6% | 5.8% | 5.0% |
| 9 | ❌ | Bollinger breakout + volume | popular | 1895 | 35.1 | 15.7 | +0.18% | -0.37% | +0.51% | -0.28% | 2.6% | 8.8% | 16.5% |
| 10 | ❌ | Minervini trend template breakout (PKScreener-style) | popular | 865 | 34.0 | 21.2 | +0.29% | -0.39% | +0.9% | -0.44% | 2.3% | 10.3% | 11.7% |
| 11 | ❌ | Your bot (current rules) | baseline | 3353 | 39.3 | 9.6 | -0.02% | -0.51% | +0.21% | -0.26% | -0.7% | -2.5% | 20.9% |
| 12 | ❌ | Laplacian (curvature) turn | natural | 4421 | 32.3 | 9.3 | -0.11% | -0.54% | +0.1% | -0.22% | 1.4% | 6.0% | 18.9% |
| 13 | ❌ | RSI(2) mean reversion (Connors) | popular | 3718 | 61.3 | 4.6 | -0.05% | -0.65% | -0.05% | +0.03% | -1.0% | -4.4% | 12.6% |
| 14 | ❌ | Bot + Hurst trending filter | natural | 413 | 40.2 | 8.7 | +0.51% | -0.69% | -0.07% | +0.61% | -0.4% | -2.1% | 7.6% |
| 15 | ❌ | Fibonacci 38-62% pullback | natural | 1554 | 40.3 | 13.4 | -0.4% | -0.91% | -0.19% | -0.33% | -3.3% | 5.4% | 16.6% |
| 16 | ❌ | Gaussian-smoothed trend turn | natural | 4716 | 30.4 | 8.5 | -0.22% | -1.0% | +0.05% | -0.25% | 0.7% | 7.4% | 17.2% |
| 17 | ❌ | ML: Neural network (MLP) | ml | 2545 | 40.2 | 10.3 | -0.17% (-0.25..-0.06) | -1.09% | +0.19% | -0.21% | 2.9% | 8.7% | 18.0% |
| 18 | ❌ | ML: Logistic regression | ml | 1638 | 38.4 | 10.4 | +0.11% | -1.64% | +1.24% | -0.1% | 8.0% | 14.9% | 11.4% |
| 19 | ❌ | ML: Random forest | ml | 1891 | 39.4 | 10.1 | +0.31% (0.19..0.48) | -1.7% | +0.96% | -0.02% | 2.8% | 4.4% | 13.2% |
| 20 | ❌ | ML: Gaussian naive Bayes | ml | 1688 | 40.7 | 10.8 | -0.68% | -1.93% | -0.57% | -0.3% | -0.4% | 5.4% | 18.1% |
| 21 | ❌ | ML: Gradient boosting | ml | 2637 | 39.8 | 9.8 | -0.05% (-0.11..-0.01) | -2.01% | +0.16% | -0.09% | 0.1% | -3.0% | 15.1% |
| 22 | ❌ | ML: Gradient boosting (basic features only) | ml | 2897 | 39.9 | 9.9 | +0.04% (-0.04..0.08) | -2.04% | +0.23% | -0.09% | 3.4% | 3.3% | 13.0% |
| 23 |  | Random entries (40 runs, median) | control | 1954 | - | - | +0.09% | - | - | - | 2.4% | 3.8% | - |
| 24 |  | NIFTY 50 buy-and-hold | control | - | - | - | 0.0% | - | - | - | 5.0% | 5.0% | 16.5% |

For ML models and the crossover families the numbers are averages over seeds / lookback pairs (range of edge in brackets), and the worst case is the weakest one.

## Do Fibonacci / prime numbers matter? (SMA crossovers)

| Family | Pair | Trades | Edge / month | Worst case | 1st half | 2nd half |
|---|---|---|---|---|---|---|
| Fibonacci | 8/21 | 3092 | +0.38% | -0.08% | +0.99% | -0.35% |
| Fibonacci | 13/34 | 1842 | +0.77% | +0.32% | +2.13% | -0.07% |
| Fibonacci | 21/55 | 1166 | +0.99% | +0.36% | +3.13% | +0.45% |
| Fibonacci | 34/89 | 724 | +0.87% | +0.37% | +3.09% | +1.07% |
| Prime | 7/23 | 2940 | +0.46% | -0.01% | +1.22% | -0.39% |
| Prime | 11/37 | 1789 | +0.91% | +0.4% | +2.33% | +0.25% |
| Prime | 19/53 | 1209 | +1.12% | +0.54% | +3.38% | +0.67% |
| Prime | 31/89 | 735 | +0.78% | +0.31% | +2.98% | +0.62% |
| Round | 10/25 | 2525 | +0.73% | +0.27% | +1.78% | -0.26% |
| Round | 15/35 | 1770 | +0.78% | +0.21% | +2.11% | +0.01% |
| Round | 20/50 | 1262 | +0.98% | +0.44% | +2.94% | +0.5% |
| Round | 30/90 | 733 | +0.81% | +0.28% | +3.27% | +0.38% |
| Random numbers | 26/84 | 801 | +0.91% | +0.28% | +3.72% | +0.32% |
| Random numbers | 10/33 | 2002 | +0.73% | +0.25% | +2.06% | -0.22% |
| Random numbers | 32/87 | 739 | +0.85% | +0.38% | +3.25% | +0.71% |
| Random numbers | 5/91 | 1363 | +0.82% | +0.37% | +2.58% | +0.29% |

If the Fibonacci and prime rows look no better than the round and random-number rows, the 'special numbers' carry no information — only the rough lookback length matters.

## What the random forest paid attention to (latest model)

| Feature | Importance |
|---|---|
| idx_vol20 | 0.274 |
| idx_ret20 | 0.169 |
| hurst | 0.077 |
| idx_d_sma50 | 0.072 |
| ret60 | 0.044 |
| lr_angle20 | 0.040 |
| d_sma200 | 0.038 |
| atr_pct | 0.031 |
| d_high252 | 0.029 |
| skew60 | 0.024 |
| fib_pos55 | 0.023 |
| rs63 | 0.019 |
| d_sma50 | 0.018 |
| ret20 | 0.018 |
| fft_slope | 0.013 |

Features starting with idx_ describe the whole market (NIFTY), not the stock. Compare 'Gradient boosting' with 'Gradient boosting (basic features only)': if the Fourier/Gaussian/Laplacian/Fibonacci/Hurst features don't raise the edge, they add no real information.

## Before acting on this

- 24 rows were tested; the best of many ideas is partly lucky by construction. Only ✅ rows deserve attention, and even those should be paper-traded first.
- Survivorship bias: the stock list is today's large caps, which flatters every long-only strategy a little.
- Run time 7 min.