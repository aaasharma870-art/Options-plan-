# Daily Regime Monitor

**Goal:** every trading morning at 09:00 ET, look up 4 numbers, compute a 0-6 score, and decide which bots can trade today.

You don't need to re-run the delta-optimizer pipeline daily. Just track these inputs:

## The 4 inputs (all free, no Polygon dependency)

| Input | Where to read it | Update frequency |
|---|---|---|
| **VIX close** | TradingView ticker `VIX` or Yahoo `^VIX` | Daily after close |
| **VIX/VIX3M ratio** | Compute: VIX close / VIX3M close (Yahoo `^VIX` and `^VIX3M`) | Daily after close |
| **VIX 252-day percentile** | Where today's VIX sits in the trailing-year distribution. Use TradingView's "Percent rank" study with length=252 on `VIX` | Daily after close |
| _(deferred)_ SPX Net GEX | Not in your Polygon plan; would require Options Developer subscription. Use SpotGamma free daily email or skip. | _optional_ |

## The 3-factor score (GEX dimension deferred — see `validation_summary.md`)

| Dimension | 0 (Green) | +1 (Yellow) | +2 (Red) |
|---|---|---|---|
| VIX level | < 17 | 17-22 | > 22 |
| IV Percentile (252d on VIX) | 50-80 | 30-50 OR 80-90 | < 30 OR > 90 |
| VIX/VIX3M | < 0.95 | 0.95-1.00 | > 1.00 |

**Composite range: 0-6**
- 0-1 → **GREEN** (most bots can trade)
- 2-3 → **YELLOW** (most bots can still trade)
- 4-5 → **ORANGE** (only iron-butterfly may enter; ICs hold but don't enter)
- 6 → **RED** (close all open positions per `regime_flip_exit` rule; halt new entries)

## Daily worked example

Suppose at end of trading on a typical day:
- VIX close: 18.5 → score 1 (yellow)
- VIX 252d-percentile: 65% → score 0 (green)
- VIX/VIX3M: 0.94 → score 0 (green)
- **Composite: 1 → GREEN** → all bots can trade tomorrow.

Now suppose VIX has spiked:
- VIX close: 31 → score 2 (red)
- VIX 252d-percentile: 95% → score 2 (red)
- VIX/VIX3M: 1.08 → score 2 (red)
- **Composite: 6 → RED** → close everything, no new entries until score recovers.

## The webhook hook

For the OA bots to actually USE this signal, you need to push the regime score into OA via webhook. Three options:

1. **TradingView alert with webhook URL** (cleanest). Build a Pine Script that computes the 3-factor score and triggers an alert with body `{"regime_score": <value>}`. OA scanner reads the webhook payload via the "External signal" filter.

2. **Manual daily entry** (simplest). Each morning, set the per-bot "Halt new entries" flag manually based on the regime score. Tedious but bulletproof.

3. **Cron + IFTTT/Zapier** (in-between). Run a 5-line Python script daily that reads VIX from a free API and pings a webhook with the score.

Option 1 is the goal. Option 2 works for a 1-2 week paper-trading bootstrap.

## When to re-run the full pipeline

You don't need to. The pipeline produces TUNED bot params; once they're in OA, they're set. Re-run only when:
- A meaningful market regime persists for 60+ days that wasn't in the 2023-2026 calibration window (e.g., a year-long bull market with no volatility).
- Polygon data history grows enough that adding it would change the gates by more than ±10%.
- You upgrade to real-chain data (Polygon Options Developer or Flat Files) — at that point re-run Phases 2-5 with the real chain to recalibrate.
