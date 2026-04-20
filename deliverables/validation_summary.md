# Validation Summary — what to trust and what to discount

This is the honest version. The numbers in `bots/<bot>/performance.md` and `suite_summary.md` are SYNTHETIC backtest outputs. They are useful for **relative ranking** between bots and **gate-level validation**, but the **absolute** P&L / Sharpe / WR figures should be discounted before being used for live capital sizing.

## What's solid (high confidence)

1. **Cross-period robustness.** Every accepted Phase 3 bot wins ≥4 of 5 CPCV folds (1 wins all 5). This means the strategy doesn't depend on a single 2023 / 2024 / 2025 sub-window. Synthetic chain calibration doesn't affect this — the relative period-vs-period comparison is meaningful.

2. **Regime gate validation (Phase 1 ANOVA).** Forward 5-day realized vol differs by Cohen's d = 1.49 between GREEN and RED regime buckets, p = 1.13e-29. Real VIX data; no synthetic anything. **The regime score is a real signal.**

3. **Stress test conclusion.** The April 2025 VIX-spike window — the period equivalent to the original $9k blowup — produces +$6,335 P&L for the regime-gated portfolio with $1,719 max drawdown. The thesis ("the bot suite needed regime gates") is empirically demonstrated.

4. **Differentiation.** The legacy Aryan Optimized bot has < 0.7 daily-PnL correlation with EVERY new Phase 3 bot. The mean-variance optimizer's weight assignments validate which bots are genuinely additive vs which are noise.

5. **OA buildability (C1).** Every bot in the suite passes the OA-DSL compatibility validator. Every entry filter and exit type is expressible in OA's UI. No calendars / diagonals / strangles / straddles / ratios.

## What to discount (lower confidence)

1. **Absolute P&L numbers.** The synthetic chain (BSM + VIX-as-IV + SKEW-skew + stress-clip patch) underestimates jump risk and tail losses. Even after the calibration patch, Optuna found parameter corners that partially dodge the corrections. Real chains would produce ~30-50% lower absolute P&L. Apply this haircut to expected returns.

2. **Win rates above 90%.** Three accepted bots show 94-96% WR. Your real Aryan Optimized bot is 77.7% on 288 real trades; Iron Butterfly is 58.5%. The 90%+ values are synthetic-clean. Expect 70-85% WR on real chains.

3. **DSR_z values in the 10^8 range.** This is a Z-score (observed_sr - expected_max) / SE — it's mathematically real but reflects synthetic Sharpes inflated by clean-loss-distribution. Treat anything DSR_z > 100 as "passes C2 by huge margin" — they're all in this regime.

4. **Profit factors above 5.** Real credit-spread bots typically run PF in the 1.5-3.0 range. Anything above that in the synthetic backtest should be discounted.

## What's missing (acknowledged gaps)

1. **C3 PBO (Probability of Backtest Overfitting) was DEFERRED.** Proper PBO requires an M(trials) × N(folds) IS/OOS matrix — adds ~5x compute per proposal. Fast-path Phase 3 ran C2 + C4 + C5 only. CPCV (C4) catches a similar overfit failure mode (best-of-IS underperforms OOS) so the gap is not catastrophic, but it IS a discipline shortfall vs the master prompt's spec.

2. **GEX dimension still deferred.** Master prompt called for a 4-factor regime score (VIX level, IV percentile, VIX/VIX3M, SPX Net GEX). We ran 3-factor (no GEX) because Polygon Stocks/Options Starter denies the option chain OI data needed to compute GEX. Adding GEX would tighten the regime gates further.

3. **Real-chain validation pending.** Polygon Stocks Starter + Options Starter denies per-contract historical aggs (403). Real-chain replacement requires either (a) Polygon Options Developer plan upgrade, (b) Polygon Flat Files S3 add-on, or (c) different data vendor (Theta Data, CBOE DataShop). All paid. The synthetic chain is a stand-in; numbers shift when real chains are swapped in.

4. **True multi-bot event-driven simulator NOT built.** Phase 4 portfolio aggregator runs each bot independently then sums daily P&Ls. This means: (a) per-underlying position cap (4 max) is post-hoc estimate only, (b) portfolio max 35% BPR is post-hoc estimate only. In stressed periods where multiple bots fire on the same underlying simultaneously, true execution would be tighter than what's reported.

5. **Iron Butterfly Legacy / Credit Scanner V3 / Trade Ideas suite NOT modeled.** Phase 4 included only Aryan Optimized as a representative legacy. Credit Scanner V3 needs GEX (deferred). Iron Butterfly needs intraday (0DTE) simulator (engine is daily-bar). Trade Ideas suite is too vague to faithfully reconstruct.

## Reading the per-bot files

When you read `bots/<bot>/performance.md`:
- **Trust**: CPCV folds-won column, the cross-period stability of P&L sign, the relative ranking between bots, the OA-buildable compatibility check.
- **Discount**: absolute P&L, raw Sharpe, DSR_z magnitudes, single-period max DD.
- **Adjust before live sizing**: divide expected annualized return by ~2; expect 2-3× the reported max DD on real chains.

## When to re-run validation

After 2-4 weeks of paper trading on a real OA bot, compare actual paper-trade WR / PF / DD to the bot's `performance.md` predictions. If actual is within ±15% of predicted on all three, the synthetic backtest is more trustworthy than feared. If actual diverges > 30% on any of the three, the synthetic chain is too far off and you should not promote that bot to live until either (a) the parameters are re-tuned against real paper-trade data, or (b) you upgrade Polygon and re-run Phases 2-4 with real chains.
