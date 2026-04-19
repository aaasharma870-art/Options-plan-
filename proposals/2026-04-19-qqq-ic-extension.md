# QQQ Iron Condor — Class A Extension of Aryan Optimized

**bot_id:** `qqq_ic_extension`
**status:** thesis (pre-backtest)
**created:** 2026-04-19

## 1. Regime finding it exploits

Phase 1 regime classifier was built and validated on SPY-centric vol data (VIX = SPY 30d ATM IV). QQQ's correlation with SPY is high (~0.85-0.95 daily) but its volatility surface is structurally different: QQQ has higher realized vol (Nasdaq concentration, semis exposure), wider bid-ask, and earlier reaction to single-name earnings (NVDA, MSFT, AAPL, GOOGL all are top-10 weights).

The aggressive gate set proven effective on SPY in Phase 2 should approximately transfer to QQQ — both are index ETFs in Class A. The differentiation between this bot and the SPY tight IC is at the underlying level, not the strategy level. This addresses the master prompt's bot-idea source #4: "Underlying class extensions."

## 2. Economic mechanism

Same Phase 2 regime gates (VIX-derived — applied to QQQ via the index correlation). Same 16Δ/5Δ wings, same 30-45 DTE window. The two adjustments for QQQ:
- Slightly higher allocation per trade because QQQ premium is ~1.3× SPY premium for equivalent deltas
- 5-DTE shorter time exit (close at DTE=14 vs DTE=21) because QQQ tail-risk events resolve faster (single-name earnings drive rapid mean reversion)

The economic edge is **diversification of premium-collection across two correlated but distinct vol surfaces**. When SPY trades a tight range and QQQ ranges wider, the QQQ IC collects more credit but carries more risk — net Sharpe similar.

## 3. Predicted performance

- Trade frequency: ~140-180/year
- Win rate: 73-80%
- Profit factor: 1.5-2.2
- Average winner: $50-100
- Average loser: $-200 to $-340
- Max drawdown: 13-18% of allocated capital
- Annualized return on $12k allocation: 30-45%

## 4. Failure mode

QQQ-specific risks:
- Mega-cap earnings clustering (e.g., Q4 reporting week with NVDA/MSFT/META/GOOGL all in 5 days). VIX may not move much; QQQ does. The regime gate doesn't catch this. Expected loss: $-400 to $-700 if open during bad-news cluster.
- Single-name news that disproportionately moves QQQ (e.g., NVDA guidance shock). 30-45 DTE IC can have ~$-400 markdown overnight on a -5% QQQ gap.
- Sector rotation away from tech (SPY drifts up while QQQ drifts down). The IC mark deteriorates over weeks rather than days. 6-week drawdown could be 10-15%.

## 5. Differentiation vs existing bots

| Existing bot | This proposal | Expected daily-PnL correlation |
|---|---|---|
| Aryan Optimized (SPY 30-45 DTE) | Different underlying | 0.5-0.7 (high index correlation but distinct strikes/timing) |
| All others | Different underlying AND structure family | < 0.4 |

The 0.5-0.7 correlation with Aryan Optimized is a YELLOW FLAG for C7 — borderline. Will need empirical confirmation in backtest. If correlation > 0.7, propose splitting allocation: keep Aryan Optimized at 70% size, this at 30%.

## Config

See `configs/proposals/qqq-ic-extension.yaml`.
