# Checkpoint 1 — Phase 1 regime classifier

**Date:** 2026-04-19
**Phase:** 1 — Regime Classifier
**Status:** ✅ **GATE PASSED.** Awaiting your approval to proceed to Phase 2.

---

## Result at a glance

| Metric | Value | Threshold | Result |
|---|---|---|---|
| ANOVA p-value (forward-5d-RV by bucket) | **1.13e-29** | < 0.01 | ✅ |
| Cohen's d (GREEN vs RED) | **1.489** | > 0.50 | ✅ |
| Trading days analyzed | 819 | — | (out of 1076 cached; first 252 used for IVP warmup) |

**The 3-factor regime score predicts forward 5-day realized vol with effect size 3× the gate threshold.** This is the highest-value artifact in the project per `PROJECT_BRIEF.md` — it's what would have blocked the $9k VIX-spike trades.

## Per-bucket forward 5-day annualized RV

| Bucket | n days | mean fwd RV | stddev fwd RV |
|---|---:|---:|---:|
| GREEN | 271 | 0.118 | 0.058 |
| YELLOW | 435 | 0.114 | 0.051 |
| ORANGE | 70 | **0.184** | 0.158 |
| RED | 43 | **0.249** | 0.190 |

GREEN ≈ YELLOW (both "low stress"). ORANGE jumps 60% above GREEN. RED jumps **2.1× above GREEN** with also higher variance — exactly the tail-blowup risk we want gated. The GREEN-vs-YELLOW degeneracy is fine; the score's job is to flag tail regimes, not to discriminate between two safe ones.

## What's in the score

Three factors (the master prompt's 4-factor table minus GEX):

| Dimension | Threshold (default, used in this run) |
|---|---|
| VIX level | <17 → 0,  17-22 → 1,  >22 → 2 |
| IV Percentile (252-day window on VIX, which IS SPY's 30d ATM IV) | 50-80 → 0, 30-50 or 80-90 → 1, <30 or >90 → 2 |
| VIX/VIX3M ratio | <0.95 → 0, 0.95-1.00 → 1, >1.00 → 2 |

Composite range 0-6. Buckets: 0-1 GREEN, 2-3 YELLOW, 4-5 ORANGE, 6 RED. Threshold iteration was prepared (per spec's "iterate ±3 units" escape hatch) but not needed — base thresholds passed on iteration 0.

## What's deferred

- **GEX** — the 4th dimension. Master prompt specifies "approximate SPX Net GEX (compute from SPY chain OI × BSM gamma)." This needs the historical option chain backfill — same blocker as Checkpoint 0. Phase 1 ran without it; the 3-factor score already passes the gate, and GEX can be added (without restructuring the score) once chain data lands.
- **Per-single-name IV percentile** — IVP for AAPL/MSFT/etc. Phase 1 only computed SPY-level regime (the master regime). Per-single-name IVP is a Phase 3 input for single-name bots; it needs single-name chains.

## Critical artifacts

- `data/results/.phase_1_status.json` — full numeric report
- `data/results/phase_1/regime_timeline.png` — VIX timeline with regime-colored shading + composite score bar chart
- `data/results/phase_1/features.parquet` — 1,076 rows × 12 features
- `data/results/phase_1/scored.parquet` — same + score/bucket columns

## What the chart shows

Long YELLOW stretch through 2023, then alternating GREEN/YELLOW through 2024 with one ORANGE spike (Aug 2024 VIX ~38), then a sustained RED period in **April-May 2025** where VIX hit ~52 — that is the regime structure the bot suite was untouched by because there were no gates. With the score we now have, an iron condor bot with `regime_score ≤ 3` in its entry filter would have been blocked on those days.

## Tests

- 111 unit tests green (`uv run pytest tests/unit -q`)
- 53 new in this phase: `test_regime_features.py` (24), `test_regime_score.py` (29) — every threshold has a parametrized boundary test, every formula has a known-answer hand-check, no `approx(self_output)`.

## Open question for Phase 2 entry

Phase 2 is gate discovery — needs the same kind of iron-condor backtest engine that Phase 3+ will use. That backtester needs option chains to compute realistic IC P&L per day. So Phase 2 is **blocked on the same chain-backfill decision** as the GEX dimension.

If you pick a chain backfill path now (A/B/C/D from Checkpoint 0), I can:
1. Kick off the chain pull in background.
2. Build the BSM pricer + Greeks (with hand-tested unit tests + put-call parity property test) and the iron-condor strategy module while data accumulates.
3. Run Phase 2 gate discovery once chains for the benchmark date range are populated.

That sequencing keeps you off the critical path. Otherwise we wait on the chain decision.

---

## Decision needed

✅ Approve regime classifier as-is and proceed to Phase 2 work that doesn't need chains (BSM, IC strategy module, backtest engine plumbing) → I start tonight.
🔁 Refine regime thresholds — pick a different ±3-unit perturbation and re-run.
⏸ Hold for chain backfill decision before any more phase work.
