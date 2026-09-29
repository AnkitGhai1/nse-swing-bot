# Strategy lab — 2026-09-29

109 NSE stocks, scored on **Oct 2021 – Sep 2026** (4.9 years) with your settings: ₹40,000 capital, 3 slots, 2% risk per trade, 0.30% costs per trade.

## Yardsticks

- **NIFTY 50 buy-and-hold:** 5.0% a year (worst fall 16.5%).
- **Pure luck** (random entries, 40 runs with fixed-target and trailing exits): median 3.8% a year; 95% of random runs stayed below **12.7%** (the 'luck line'); the single luckiest run made 13.5%.
- A strategy is only interesting if it beats **both**.

## Ranking (by typical yearly growth of your capital)

| # | Strategy | Type | Trades | Win % | Avg/trade | 1st half | 2nd half | Yearly growth | Bad-luck ₹ | Worst fall | Beats luck | Beats Nifty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ML: Logistic regression | ml | 1634 | 38.5 | 0.05% | 1.52% | -0.14% | 15.7% | ₹81,455 | 24.2% | ✅ | ✅ |
| 2 | SMA crossover — Random numbers lookbacks (26/84, 10/33, 32/87, 5/91) | numbers | 1226 | 34.0 | 2.63% | 4.63% | 0.16% | 15.28% (11.6..18.8) | ₹79,826 | 22.5% | ✅ | ✅ |
| 3 | Fourier cycle turn | natural | 1932 | 41.8 | 0.278% | 0.95% | -0.51% | 12.7% | ₹71,908 | 14.3% | — | ✅ |
| 4 | Minervini trend template breakout (PKScreener-style) | popular | 865 | 34.0 | 0.479% | 1.67% | -0.97% | 10.3% | ₹64,437 | 21.7% | — | ✅ |
| 5 | ML: Neural network (MLP) | ml | 2565 | 39.7 | 0.19% | 0.57% | 0.02% | 9.83% (8.2..11.7) | ₹63,263 | 23.47% | — | ✅ |
| 6 | SMA crossover — Round lookbacks (10/25, 15/35, 20/50, 30/90) | numbers | 1572 | 35.47 | 2.31% | 4.19% | 0.0% | 9.5% (6.9..13.8) | ₹62,211 | 19.98% | — | ✅ |
| 7 | Bollinger breakout + volume | popular | 1895 | 35.1 | 0.36% | 1.41% | -0.81% | 8.8% | ₹60,294 | 22.4% | — | ✅ |
| 8 | Gaussian-smoothed trend turn | natural | 4716 | 30.4 | 0.076% | 0.41% | -0.29% | 7.4% | ₹56,633 | 26.9% | — | ✅ |
| 9 | SMA crossover — Prime lookbacks (7/23, 11/37, 19/53, 31/89) | numbers | 1668 | 35.95 | 2.29% | 4.04% | 0.11% | 6.0% (2.9..7.8) | ₹53,112 | 23.17% | — | ✅ |
| 10 | Laplacian (curvature) turn | natural | 4421 | 32.3 | 0.145% | 0.56% | -0.34% | 6.0% | ₹53,079 | 26.8% | — | ✅ |
| 11 | Fibonacci 38-62% pullback | natural | 1556 | 40.3 | -0.079% | 0.17% | -0.38% | 5.8% | ₹52,636 | 12.8% | — | ✅ |
| 12 | 12-1 momentum rotation (monthly) | popular | 1644 | 49.6 | 0.397% | 1.42% | -0.84% | 5.8% | ₹52,482 | 7.4% | — | ✅ |
| 13 | Turtle 55-day breakout | popular | 1261 | 31.6 | 1.635% | 3.37% | -0.45% | 5.5% | ₹51,846 | 29.4% | — | ✅ |
| 14 | ML: Gaussian naive Bayes | ml | 1688 | 40.7 | 0.34% | 0.46% | 0.31% | 5.4% | ₹51,502 | 26.1% | — | ✅ |
| 15 | NIFTY 50 buy-and-hold | control | - | - | - | - | - | 5.0% | - | 16.5% | — | — |
| 16 | ML: Random forest | ml | 1886 | 39.37 | 0.29% | 1.31% | 0.08% | 4.03% (0.9..7.1) | ₹48,600 | 25.53% | — | — |
| 17 | Random entries (40 runs, median) | control | - | - | 0.295% | - | - | 3.8% | - | - | — | — |
| 18 | Supertrend(10,3) flip | popular | 1716 | 37.6 | 1.245% | 3.06% | -0.67% | 3.8% | ₹47,968 | 16.1% | — | — |
| 19 | SMA crossover — Fibonacci lookbacks (8/21, 13/34, 21/55, 34/89) | numbers | 1706 | 35.88 | 2.19% | 3.89% | 0.09% | 0.77% (-7.0..8.2) | ₹42,759 | 25.8% | — | — |
| 20 | ML: Gradient boosting (basic features only) | ml | 2905 | 39.87 | 0.28% | 0.44% | 0.21% | 0.73% (0.2..1.6) | ₹41,246 | 32.57% | — | — |
| 21 | Bot + Hurst trending filter | natural | 413 | 40.2 | 0.084% | -0.24% | 0.54% | -2.1% | ₹33,685 | 23.0% | — | — |
| 22 | Your bot (current rules) | baseline | 3353 | 39.3 | 0.048% | 0.21% | -0.13% | -2.5% | ₹30,383 | 30.5% | — | — |
| 23 | ML: Gradient boosting | ml | 2639 | 39.7 | 0.27% | 0.75% | 0.08% | -3.9% (-8.3..0.7) | ₹33,594 | 34.77% | — | — |
| 24 | RSI(2) mean reversion (Connors) | popular | 3718 | 61.3 | 0.016% | 0.01% | 0.02% | -4.5% | ₹31,924 | 23.0% | — | — |

Yearly growth for ML models is the average over random seeds, with the range across seeds in brackets. 1st/2nd half = average return per trade in each half of the window; if one is negative the idea is fragile.

## Do Fibonacci / prime numbers matter? (SMA crossovers)

| Family | Pair | Trades | Avg/trade | Yearly growth |
|---|---|---|---|---|
| Fibonacci | 8/21 | 3092 | 0.773% | -7.0% |
| Fibonacci | 13/34 | 1842 | 1.774% | -1.3% |
| Fibonacci | 21/55 | 1166 | 2.809% | 8.2% |
| Fibonacci | 34/89 | 724 | 3.397% | 3.2% |
| Prime | 7/23 | 2940 | 0.894% | 7.1% |
| Prime | 11/37 | 1789 | 2.039% | 7.8% |
| Prime | 19/53 | 1209 | 3.067% | 6.2% |
| Prime | 31/89 | 735 | 3.143% | 2.9% |
| Round | 10/25 | 2525 | 1.395% | 13.8% |
| Round | 15/35 | 1770 | 1.877% | 7.2% |
| Round | 20/50 | 1262 | 2.863% | 10.1% |
| Round | 30/90 | 733 | 3.09% | 6.9% |
| Random numbers | 26/84 | 801 | 3.194% | 12.1% |
| Random numbers | 10/33 | 2002 | 1.618% | 18.6% |
| Random numbers | 32/87 | 739 | 3.364% | 11.6% |
| Random numbers | 5/91 | 1363 | 2.326% | 18.8% |

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

Compare 'Gradient boosting' with 'Gradient boosting (basic features only)' in the ranking: if adding Fourier/Gaussian/Laplacian/Fibonacci/Hurst features doesn't raise the out-of-sample result, they aren't adding real information.

## Read this before acting on the ranking

- 24 ideas were tested. Even if none had any edge, the best of them would look good by chance. Treat anything that doesn't clearly beat the 'luck' line with suspicion.
- Prefer ideas that are positive in **both** halves and beat both yardsticks.
- Survivorship bias: the stock list is today's large caps, which flatters every long-only strategy (and buy-and-hold) a little.
- To switch the live bot to a winning idea, ask for it to be wired in; the weekly backtest will then keep checking it.
- Run time 7 min.