# Build Order — paper-first sequence

**Goal:** validate the riskiest bots first in paper, expand to live only after each bot proves its `performance.md` predictions are within ±15% on at least 2 weeks of paper trading.

## Build sequence (do in this order)

### Phase A — Wire the regime monitor (do FIRST, before any bot)

1. Set up TradingView alert on a Pine Script that emits the 3-factor regime score daily (see `regime_monitor.md`). Webhook target: a placeholder OA endpoint (you'll wire this to specific bots in Phase B).
2. Confirm the alert fires correctly for 5 trading days. Hand-verify the score against the regime_monitor.md worked examples.
3. Optionally: have the script log to a Google Sheet for journal/audit.

**Don't build any bot until this is working.** Every bot's `regime_flip_exit` and `regime_score_max` filters depend on this signal.

### Phase B — Build & paper the most credible new bot first

Start with **`spy-iron-fly-low-vvix`** (the highest-confidence Phase 3 result):
- Most differentiated (lowest pairwise correlation with everything)
- Most realistic WR (81.6%) — closest to your real-bot baseline (77.7%)
- Lowest backtested max DD ($481)
- Mean-variance optimizer assigns it 40% (the cap)

Build per `bots/spy-iron-fly-low-vvix/oa_build_guide.md`. Paper-trade for **2 weeks minimum**. Compare actual WR / PF / DD to predicted.

### Phase C — Build the second-most-credible bot

**`spy-bear-call-post-spike-fade`** — 75.8% WR (closest to real baseline). Build, paper 2 weeks, validate.

If both Phase B and Phase C land within ±15% of predictions: synthetic chain is trustworthy enough to proceed faster. If either diverges > 30%: stop, do not build the rest, re-run Phase 3 with real chains (requires Polygon upgrade).

### Phase D — Build the legacy upgrade

**`aryan_optimized_legacy`** but with the regime gate added (i.e., upgrade your existing Aryan Optimized in OA to add the same regime gates the new bots use). This isn't a new bot — it's a regime layer over the bot you already trust. Highest confidence; smallest behavior change.

Paper-trade the upgraded version alongside the original (existing) version for 2 weeks. The upgraded should miss some entries the original takes (during RED days) and otherwise produce nearly-identical results.

### Phase E — Build the rest

Once A-D are live and stable for 4 weeks total, build the remaining 4 in this order (highest-WR-first, but synthetic-inflated so size cautiously):

1. `spy-tight-ic-aggressive`
2. `spy-bull-put-elevated-vol`
3. `spy-ic-regime-recovery`
4. `qqq-ic-extension`

For these, paper for the full 2 weeks each. Don't size them above 50% of their `allocation_usd` from `config.yaml` until you've seen them through one VIX-spike event live.

## Sizing ramp-up

For each bot:
- Week 1-2 paper: 1 contract (smallest possible)
- Week 3-4 paper: 1-2 contracts (still small)
- Promote to live: 1 contract initially
- Week 5-8 live: ramp to 2-3 contracts only if backtest predictions hold
- Week 9+ live: ramp toward `allocation_usd` cap from config.yaml

Total ramp time per bot: ~2 months from build to full size. The whole suite: ~4-6 months to fully sized.

## Halt conditions (read `portfolio_kill_switches.md`)

If any kill switch fires during paper or live trading:
- Pause the affected bot(s) immediately
- Journal the trigger event
- Do NOT advance any bots to higher size during a halted period
- Re-enable per the conditions listed

## Validation cadence

- **Weekly:** review per-bot WR, PF, max DD for the week. Compare to `performance.md` annualized predictions divided by ~52.
- **Monthly:** review aggregate suite Sharpe / max DD vs `suite_summary.md`. Reweight per mean-variance ONLY after 3 months of live data confirms the synthetic-chain ranking.
- **Quarterly:** re-run the regime classifier with the latest data; confirm the 3-factor score still passes ANOVA. Re-run Phase 2 gate discovery if new historical regime modes have appeared.

## When to scrap and rebuild

Scrap the synthetic-chain pipeline and rebuild against real chains when:
- Any single Phase B/C/D bot's actual paper WR is outside ±15% of predicted for 4 consecutive weeks.
- Aggregate suite max DD exceeds 6% in any 30-day window during paper.
- You decide to upgrade Polygon plan to Options Developer or buy Flat Files.

The path to "rebuild against real chains" is documented in the Phase 0 / Checkpoint 0 markdown — the chain ingest layer is already factored to swap in `PolygonChain` (real) for `SyntheticBSMChain` (current). Phases 2-4 can re-run once `PolygonChain` is implemented.
