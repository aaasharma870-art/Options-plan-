# SPY Iron Butterfly — Low-VVIX Gate

**bot_id:** `spy_iron_fly_low_vvix`
**status:** thesis (pre-backtest)
**created:** 2026-04-19

## 1. Regime finding it exploits

Iron butterflies are "betting on stillness" — they pin around the at-the-money body strike and lose if SPY moves significantly in either direction. They differ from ICs in that the body is at ATM (not 16Δ wings), so they collect more credit but have higher gamma exposure and pin risk.

The hidden risk is **vol-of-vol expansion**: when VVIX rises, ATM IV doesn't just rise — the entire IV surface destabilizes, and the body of the IF (which has the highest vega) sees the most violent re-pricing. Aryan's existing 0DTE Iron Butterfly is ungated against VVIX — when VVIX spiked above 120 in the April-May 2025 period (per the regime timeline chart), it almost certainly contributed to losses.

Phase 1 didn't directly score VVIX (it's the 4th factor placeholder, deferred until GEX-style modeling). But cached VVIX data from the Yahoo pull is available and addressable.

## 2. Economic mechanism

Iron butterfly entry only when:
- VVIX < 110 (vol-of-vol suppressed → IV is "anchored")
- 5-day realized SPY vol < 12% annualized (last week was tight)
- VIX/VIX3M < 0.95 (deep contango — term structure supports continued vol selling)

When all three conditions hold, the IF body has the lowest expected gamma realization. The bot collects ~$200-400 of credit per IF on SPY at 7-14 DTE and lets theta decay into expiration.

## 3. Predicted performance

- Trade frequency: ~30-50/year (gates are tight by design)
- Win rate: 55-70% (IFs have lower WR than ICs because pin risk is real)
- Profit factor: 1.4-2.0
- Average winner: $120-200
- Average loser: $-280 to $-400
- Max drawdown: 12-18% of allocated capital
- Annualized return on $10k allocation: 25-40%

## 4. Failure mode

This bot loses money when:
- Surprise overnight news on a quiet day (e.g., geopolitical event, surprise rate decision). VVIX is low going in but spikes on Day 1 of holding. Both wings get tested. Expected single-trade loss: max loss = wider wing × 100 - credit, typically $-400 to $-600.
- VVIX is statically low but skew is steepening (call-side or put-side IV diverging from ATM). The IF body holds but a wing degrades. Could be 4-6 trades in a row losing if the regime persists. Drawdown 8-12%.
- Earnings/event coincidence (FOMC, CPI, NFP) — currently blocked by the FOMC blackout filter.

## 5. Differentiation vs existing bots

| Existing bot | This proposal | Expected daily-PnL correlation |
|---|---|---|
| Iron Butterfly (existing, 0DTE, 50Δ, no VVIX gate) | 7-14 DTE, VVIX-gated, lower-frequency | < 0.5 (different DTE; different entry-day selection) |
| Aryan Optimized (30-45 DTE IC) | Different structure (IF vs IC), shorter DTE | < 0.3 |
| Credit Scanner V3 (0DTE GEX-routed) | Different DTE; gates are vol-based not GEX | < 0.3 |

The key differentiation from existing IF: this only enters when vol-of-vol AND realized are both low. The existing IF takes any 0DTE setup. The two should diverge most on VVIX-elevated days.

## Config

See `configs/proposals/spy-iron-fly-low-vvix.yaml`.
