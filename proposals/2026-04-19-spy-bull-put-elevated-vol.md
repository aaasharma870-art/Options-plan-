# SPY Bull Put Spread — Elevated VIX + Trend-Up Overlay

**bot_id:** `spy_bull_put_elevated_vol`
**status:** thesis (pre-backtest)
**created:** 2026-04-19

## 1. Regime finding it exploits

The Phase 2 IC backtest showed that the binding gates are VIX/VIX3M backwardation and IVP floor — i.e., gates that block tail regimes. But there's a complementary opportunity: regimes where VIX is elevated (rich premium) but the directional trend has already reversed positive (post-spike recovery). These are the "vol crush + drift" days that pay handsomely if you take a directional bet rather than a delta-neutral one.

Aryan's Trade Ideas suite includes a bull put scanner but it's ungated by regime score. This proposal adds the regime overlay AND a directional confirmation (SPY > 20-day SMA = trend-up confirmed).

## 2. Economic mechanism

A bull put spread (sell higher-strike put, buy lower-strike put) is bullish-to-neutral. It profits if SPY stays above the short put strike at expiration. Two edges combine:
- Vol crush: high VIX (>20) implies rich premium. Selling the put captures that.
- Drift: SPY > 20d SMA confirms uptrend. Probability of touching the short strike drops.

Entry only when: VIX > 20 (premium is rich) AND SPY > 20d SMA (trend up) AND VIX/VIX3M < 1.0 (no backwardation kicker). Short put at 16Δ, long put at 5Δ, 30-45 DTE.

The economic mechanism is **path-dependent vol crush**: when VIX is elevated post-spike, the term structure is in backwardation only briefly. Once it returns to contango (VIX/VIX3M < 1.0), the implied dynamics suggest a 5-15 vol-point compression over the next 20-30 days. The bull put captures both the put-side IV crush AND the upward drift.

## 3. Predicted performance

- Trade frequency: ~40-60/year (gate is tight — needs elevated VIX with trend-up)
- Win rate: 78-85% (verticals have higher WR than ICs because only one side has risk)
- Profit factor: 1.6-2.4
- Average winner: $60-110 per spread
- Average loser: $-280 to $-380
- Max drawdown: 8-12% of allocated capital
- Annualized return on $8k allocation: 28-42%

## 4. Failure mode

This bot loses money when:
- The VIX-elevated regime persists into a real downtrend (e.g., 2022 Q1: SPY topped at ~480, VIX>20, then SPY trended down for 9 months). The 20d SMA filter is BROKEN by sustained downtrend; the bot stops entering, but any open positions take losses. Expected: 2-3 losers in a row, 5-8% drawdown.
- VIX spike-then-spike (e.g., a vol regime with multiple spikes 2-3 weeks apart). Bull put closes for loss on first spike, gate clears after a week, re-enters, closes again. Expected: 6-10% drawdown over 4-6 weeks.
- Black-swan single-day -5% SPY move. Max loss = wing × 100 - credit ≈ $-380.

## 5. Differentiation vs existing bots

| Existing bot | This proposal | Expected daily-PnL correlation |
|---|---|---|
| Trade Ideas Scanner V1 bull put | Adds regime + trend gates; same structure | 0.4-0.6 (overlapping in some entries, divergent in many) |
| Aryan Optimized (IC) | Different structure (one-sided vs neutral) + different gate logic | < 0.4 |
| All others | Different structure | < 0.3 |

## Config

See `configs/proposals/spy-bull-put-elevated-vol.yaml`.
