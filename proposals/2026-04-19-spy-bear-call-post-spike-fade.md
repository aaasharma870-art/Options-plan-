# SPY Bear Call Spread — Post-Spike Fade

**bot_id:** `spy_bear_call_post_spike_fade`
**status:** thesis (pre-backtest)
**created:** 2026-04-19

## 1. Regime finding it exploits

Phase 1's regime timeline chart shows multiple short-lived RED periods (single-day or 2-3-day VIX spikes followed by recovery). After a sharp VIX spike, two empirical patterns emerge:
- The spike is usually fade-able within 5-10 trading days as the news catalyst is digested.
- The first failed-rally / lower-high pattern that follows the spike often produces a downward retest before the eventual recovery. This is the classic "second leg lower" that traps buyers of the dip.

Bear call spreads are bearish-to-neutral and profit when SPY fails to rally to the short call strike. They are the directional opposite of bull puts and complement them in a portfolio.

This is a **timing edge** strategy (Phase 3 §3a #2): entries are conditional on a recent VIX spike (timing filter) AND a failed bounce (technical filter).

## 2. Economic mechanism

Entry only when:
- VIX 1d change > +15% in the LAST 5 trading days (spike has happened recently)
- SPY < 5-day SMA (rally has failed, price below short-term mean)
- VIX/VIX3M between 0.95 and 1.05 (transition zone — backwardation is breaking)
- IVP > 40 (premium is rich post-spike)

Short call at 16Δ, long call at 5Δ, 14-21 DTE (shorter than IC because the post-spike fade window is narrow). The economic edge is **directional vol crush**: post-spike, IV is high (rich credit), and the technical setup suggests another 1-2% downside before stabilization. Both vol crush and adverse drift work in the bot's favor.

## 3. Predicted performance

- Trade frequency: ~25-40/year (gate is restrictive — requires post-spike-and-failed-bounce)
- Win rate: 72-82%
- Profit factor: 1.4-2.0
- Average winner: $50-90 per spread
- Average loser: $-260 to $-360
- Max drawdown: 10-15%
- Annualized return on $7k allocation: 22-38%

## 4. Failure mode

This bot loses money when:
- "V-shaped recovery" — VIX spikes, market bottoms, rips back up faster than expected. Bot enters on the failed bounce, market rallies through the short call. Worst case: single trade -$360.
- Multi-week vol regime where each spike-fade cycle produces a higher VIX peak (e.g., the early COVID period). Bot enters, gets stopped, re-enters, gets stopped again. 4-6 losers in 3 weeks → 8-12% drawdown.
- Liquidity dry-up post-spike (real bid-ask widens past the synthetic chain's modeled spread). Stop-loss closes at worse-than-modeled prices. Expected slippage: 5-10% of credit per trade.

## 5. Differentiation vs existing bots

| Existing bot | This proposal | Expected daily-PnL correlation |
|---|---|---|
| Trade Ideas bear call | Adds explicit post-spike + failed-bounce gates | 0.3-0.5 (different entry timing) |
| Aryan Optimized (delta-neutral IC) | Directional bias (bearish) | < 0.2 (often inverse correlation on rally days) |
| spy_bull_put_elevated_vol (this batch) | Opposite directional bias | -0.4 to -0.6 (often runs opposite to bull put on directional days) |

The negative correlation with the bull put proposal is a feature: when paired, they hedge each other's directional risk.

## Config

See `configs/proposals/spy-bear-call-post-spike-fade.yaml`.
