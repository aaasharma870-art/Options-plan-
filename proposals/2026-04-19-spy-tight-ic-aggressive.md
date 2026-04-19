# SPY Tight Iron Condor — Aggressive Gate

**bot_id:** `spy_tight_ic_aggressive`
**status:** thesis (pre-backtest)
**created:** 2026-04-19

## 1. Regime finding it exploits

Phase 1 established (Cohen's d = 1.49 for forward-5d-RV between GREEN and RED) that the 3-factor regime score discriminates safe-to-trade days from blowup days. Phase 2's Pareto frontier showed the binding gates are **VIX/VIX3M backwardation (kill switch)** and **IVP floor**, not absolute VIX level.

Aryan Optimized currently runs ungated (regime-blind). Its 77.7% WR is good but its $9k VIX-spike loss came entirely from days the regime score would have classified RED. A regime-gated, structurally tighter IC should dominate Aryan Optimized on a risk-adjusted basis.

## 2. Economic mechanism

Tighter deltas (12Δ short / 4Δ long vs Aryan Optimized's 16-20Δ/5Δ) move the strikes farther from the money. Combined with a shorter DTE window (21-35 vs 30-45), this:
- Cuts max-profit per trade (smaller credit) but
- Cuts loss probability per trade more than proportionally (12Δ short = 88% prob OTM at expiry vs 84% at 16Δ — but the loss CONDITIONAL on touching is smaller because there's less assignment risk)
- Reduces gamma exposure (shorter DTE + farther OTM = less convex payoff)
- Allows faster cycling — 35% profit target instead of 50% means 4-7 day average holding period vs Aryan's 14-21

Combined with the aggressive regime gate (VIX≤28, VIX/VIX3M≤1.0, 10d-high≤35, 1d-change≤25%, IVP≥20), the bot trades only when short-vol premium is rich AND not in a tail regime.

## 3. Predicted performance

- Trade frequency: ~150-180/year (calibrated chain shows ~316 over 825 trading days for the aggressive-gated benchmark; tighter deltas reduce eligibility further)
- Win rate: 78-85% (tighter deltas raise win probability per trade)
- Profit factor: 1.8-2.5
- Average winner: $40-80 per IC
- Average loser: $-180 to $-280
- Max drawdown: 10-15% of allocated capital across 4 years
- Annualized return on $10k allocation: 35-55%

## 4. Failure mode

This bot loses money when:
- Sustained tight-range volatility expansion (VIX rising slowly without backwardation, IVP staying mid-range). The regime gate doesn't trigger but realized vol grinds up — the tight wings (4Δ long = $5-7 wide) get tested and IC enters loss. Expected drawdown in this scenario: 8-12% over 6-8 weeks.
- Gap-down without VIX backwardation kicker. SPY drops 3% overnight on news; VIX/VIX3M doesn't immediately invert; gate is open at next entry. Expected single-trade loss: $-280 to $-400 (max loss = wing×100 - credit ≈ $580 on a 5-wide wing at $20 credit).

## 5. Differentiation vs existing bots

| Existing bot | This proposal | Expected daily-PnL correlation |
|---|---|---|
| Aryan Optimized (30-45 DTE, 16-20Δ short, no gate) | Different DTE window AND deltas AND has regime gate | < 0.6 (different timing of trades, no overlap on RED days) |
| Iron Butterfly (0DTE, 50Δ) | Completely different DTE + structure | < 0.2 |
| Credit Scanner V3 (0DTE GEX-routed SPY) | Different DTE | < 0.2 |
| Trade Ideas (mixed verticals) | Different structure (IC vs vertical) | < 0.4 |

Passes C7 differentiation provisionally. Will be confirmed by post-backtest correlation matrix.

## Config

See `configs/proposals/spy-tight-ic-aggressive.yaml`.
