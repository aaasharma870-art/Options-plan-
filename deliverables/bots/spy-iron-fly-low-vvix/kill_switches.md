# Kill Switches — spy-iron-fly-low-vvix

## Bot-specific halts (in addition to portfolio-wide rules)

1. **VIX 1-day spike**: If VIX rises > 30% in a single session, halt new entries for 48 hours regardless of regime score.

2. **Personal account drawdown**: If your TOTAL OA account drawdown crosses
   -5% from its monthly peak, pause this bot until you manually re-enable.
   This is a discretionary safeguard, not a backtested rule.

3. **Bot-specific drawdown**: If THIS bot's running P&L drops > 50% of its
   YTD peak, pause new entries pending a manual review.

4. **Liquidity warning**: If the bot scans but consistently fails to find
   contracts meeting the min-credit + max-bid-ask criteria for 5 consecutive
   days, the surface is too thin — pause and re-check parameters.

5. **Regime-flip exit (already in OA build guide)**: When the
   `regime_score_max` webhook signal flips above the configured threshold,
   close all open positions immediately. This is the single most important
   rule — it's what would have prevented the original $9k blowup.

## Re-enable conditions

- Wait until VIX < 22 AND VIX/VIX3M < 1.0 for 3 consecutive trading days.
- Aryan account drawdown back to within 2% of monthly peak.
- Manually inspect the regime timeline (`regime_monitor.md`) for the trigger event.

## Logging

Every halt event should be logged in your bot journal with:
- Date, time, trigger condition that fired
- Account state at trigger (open positions, BPR, P&L)
- Subsequent re-enable date and rationale
