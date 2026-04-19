# SPY Iron Condor — Regime Recovery (post-RED entry)

**bot_id:** `spy_ic_regime_recovery`
**status:** thesis (pre-backtest)
**created:** 2026-04-19

## 1. Regime finding it exploits

Phase 1's regime timeline shows the post-spike vol crush is one of the highest-quality short-vol windows: VIX has just spiked (premium is rich), regime has just transitioned from RED back to YELLOW or GREEN (forward vol expectation has dropped), and most market participants are still psychologically de-risked.

Specifically, Phase 1 forward-5d-RV statistics by bucket (from `data/results/.phase_1_status.json`):
- RED forward-5d-RV mean: 0.249
- GREEN forward-5d-RV mean: 0.118
- The transition from RED → GREEN/YELLOW marks an inflection where forward expected vol drops by ~50%.

This is the master prompt's bot idea #5: regime-transition strategy.

## 2. Economic mechanism

Entry only on the day the regime score TRANSITIONS from {ORANGE, RED} on day T-1 to {GREEN, YELLOW} on day T. Standard 16Δ/5Δ IC, 30-45 DTE. The economic edge is **front-running the vol-crush re-pricing**: on the transition day, ATM IV (=VIX) has dropped from its peak, but the back of the curve hasn't fully re-anchored yet. The IC sells premium that's still elevated relative to where vol will settle.

Exit on first regime flip back to ORANGE/RED (don't ride the next spike), or at standard PT/SL/time exit, whichever first.

## 3. Predicted performance

- Trade frequency: ~20-35/year (transitions are rare events — Phase 1 chart shows ~25-30 per year)
- Win rate: 80-88%
- Profit factor: 2.0-3.0 (high WR + decent reward)
- Average winner: $80-140
- Average loser: $-240 to $-340
- Max drawdown: 6-10%
- Annualized return on $8k allocation: 20-35%

## 4. Failure mode

This bot loses money when:
- "False recovery" — regime score transitions to GREEN, then immediately re-elevates to RED within 2-3 days. Bot enters on the transition day, gets stopped within a week. Expected: 1-2 losers per false recovery. Annualized cost: 2-4 trades × $-280 = $-560 to $-1120.
- Multi-spike regime where transitions happen but never stabilize (e.g., March 2020). Bot may enter 4-5 times across 6 weeks, each closing at modest loss or scratch. Drawdown: 5-8%.
- Late entry — by the time the regime score officially transitions (end-of-day), the next-day open may have gapped up. The bot enters at lower premium than expected. Marginal degradation, not catastrophic.

## 5. Differentiation vs existing bots

| Existing bot | This proposal | Expected daily-PnL correlation |
|---|---|---|
| Aryan Optimized (no regime gate) | Trades only on rare transition days | < 0.3 (very narrow trade-day overlap) |
| Iron Butterfly (0DTE) | Different DTE | < 0.2 |
| spy_tight_ic_aggressive (this batch) | Different gate (transition vs daily aggressive) | < 0.4 (could overlap on a few transition days) |
| Credit Scanner V3 | Different DTE | < 0.2 |

This bot is one of the most differentiated by design — its trade calendar is a tiny subset of any other bot's. C7 should be cleared comfortably.

## Config

See `configs/proposals/spy-ic-regime-recovery.yaml`.
