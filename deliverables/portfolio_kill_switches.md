# Portfolio-Wide Kill Switches

These are the suite-level halts that trump every individual bot's gates. When any of these fires, **close everything and stop entering new positions.**

## The non-negotiables (auto-halt)

1. **VIX/VIX3M backwardation > 1.05.** This is the single strongest tail signal. The April 2025 VIX spike crossed 1.10. The original $9k loss happened entirely on backwardated days.

2. **Account-level drawdown > 5% from monthly peak.** Halt all new entries until either (a) account recovers to within 2% of monthly peak, OR (b) you manually re-enable after a journaled review.

3. **Regime score RED for 3 consecutive trading days.** A single RED day is noise; three in a row is a regime change. Stop entering even at GREEN/YELLOW transitions until you've had a YELLOW or GREEN close.

## The discretionary halts (manual judgment)

4. **Geopolitical event window.** Major geopolitical news (war, central-bank emergency action, sovereign default) — pause for 48 hours. The synthetic chain doesn't model these.

5. **Earnings concentration week.** Mega-cap earnings clustering (Q1/Q3 reporting weeks where NVDA, MSFT, META, GOOGL, AMZN report within 5 days) — close QQQ-IC bot specifically; SPY bots can continue.

6. **FOMC meeting day, CPI release, NFP release.** Already enforced in per-bot `fomc_cpi_nfp_blackout`, but verify before market open. Don't enter the day BEFORE either.

7. **OA platform downtime.** If OA's bot engine is down, manual position monitoring required. Don't open new positions if you can't see them.

## Re-enable conditions (per halt type)

| Trigger | Condition to re-enable |
|---|---|
| VIX/VIX3M > 1.05 | Ratio < 1.0 for 2 consecutive trading days |
| Account DD > 5% | DD recovered to within 2% AND you've journaled the cause |
| RED for 3 consecutive days | First YELLOW or GREEN close after a RED period |
| Geopolitical event | 48 hours elapsed AND VIX < 22 AND no new related news |
| Earnings cluster | Cluster window ends |
| FOMC/CPI/NFP | Day after the release |
| OA downtime | OA confirms platform restored AND open positions accounted for |

## The override rule

If you are uncertain whether to halt, halt. Re-entering after a missed opportunity is a non-event. Trading through a kill-switch trigger is how the $9k blowup happened.
