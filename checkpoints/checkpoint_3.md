# Checkpoint 3 — Phase 3a thesis drafts

**Date:** 2026-04-19
**Phase:** 3a — Bot Maker (thesis generation only; no backtests yet)
**Status:** 6 of max-10 proposals drafted. Awaiting your approval on which to proceed to 3b (Optuna tuning).

---

## Synthetic chain calibration update (between Checkpoint 2 and now)

You called out that Phase 2's 93% WR was sketchy. Patched the synthetic chain with stress-clipped IV + asymmetric down-move multiplier + steeper put-skew on stress days. Re-ran the aggressive gate as calibration:

| Metric | Pre-patch (sketchy) | Post-patch (calibrated) | Real Aryan Optimized |
|---|---|---|---|
| WR | 93.0% | **75.9%** ✅ | 77.7% |
| PF | 7.2 | 1.96 | 2.77 |
| Max DD | $4,200 | $5,731 | (had $9k VIX-spike loss) |
| CVaR-95 | -$177 | -$1,890 | — |
| Worst trade | $-X | $-4,425 | $-9,000 (VIX spike) |
| Worst-day dates | (clean) | Apr-May 2025 spike days | matches your real loss period |

**Calibrated chain is now in production for Phase 3.** Phase 2 coarse grid is re-running in the background with the new chain (~15 min) — `configs/gate_sets.yaml` will get an updated metric table once it finishes. The gate THRESHOLDS will not change much (those were robust to chain calibration); only the absolute metrics shift toward realism.

---

## The 6 proposals

All 6 thesis files are in `proposals/2026-04-19-*.md`; all configs in `configs/proposals/*.yaml`.

| # | Bot ID | Structure | Gate | Underlying | Predicted WR | Diff vs existing |
|---|---|---|---|---|---|---|
| 1 | `spy_tight_ic_aggressive` | IC 12Δ/4Δ 21-35 DTE | Aggressive | SPY | 78-85% | < 0.6 vs Aryan Opt (different DTE+deltas+gate) |
| 2 | `spy_iron_fly_low_vvix` | IF 50Δ/10Δ 7-14 DTE | Aggressive + VVIX<110 + RV5d<0.12 | SPY | 55-70% | < 0.5 vs existing IF (gates existing IF doesn't have) |
| 3 | `qqq_ic_extension` | IC 16Δ/5Δ 30-45 DTE | Neutral | QQQ | 73-80% | 0.5-0.7 vs Aryan Opt (borderline; needs empirical confirm) |
| 4 | `spy_bull_put_elevated_vol` | Bull put 16Δ/5Δ 30-45 DTE | Neutral + VIX>20 + SPY>20dSMA | SPY | 78-85% | < 0.6 vs Trade Ideas bull put (regime overlay added) |
| 5 | `spy_bear_call_post_spike_fade` | Bear call 16Δ/5Δ 14-21 DTE | Aggressive + VIX 5d-spike + SPY<5dSMA | SPY | 72-82% | -0.4 to -0.6 vs proposal #4 (hedges) |
| 6 | `spy_ic_regime_recovery` | IC 16Δ/5Δ 30-45 DTE | Regime transition RED→GREEN/YELLOW | SPY | 80-88% | < 0.3 vs all (rare entry days) |

**Coverage of strategy types:**
- Iron condors: #1, #3, #6 (different gates / underlyings / timing)
- Iron butterfly: #2
- Bullish vertical: #4
- Bearish vertical: #5

**Coverage of regime archetypes:**
- "Always-on" (Aggressive gate): #1, #2 (with extra filters), #5
- "Restricted" (Neutral gate): #3, #4
- "Event-driven": #5 (post-spike), #6 (regime flip)

**Differentiation matrix (predicted, will be confirmed in 3c):**
- Most differentiated by design: #6 (rare transition entries), #2 (VVIX-gated)
- Borderline C7 risk: #3 (QQQ IC vs SPY Aryan Optimized — high index correlation)
- Naturally hedging: #4 ↔ #5 (bull put + bear call should run inversely on directional days)

## Held back from this round (room for 4 more in Phase 3a if you want)

Slot still open for:
- IWM iron condor (small-cap divergence play)
- Single-name IC on AAPL or MSFT (Class B with -3Δ shift)
- 0DTE timing-edge IC on SPY (10:30 AM scan, GEX overlay — currently blocked by GEX deferral)
- Asymmetric IC (skewed deltas based on directional regime tilt)

I held these to keep the first round focused. Add them in if you'd like more breadth, but the current 6 already span all 4 OA-buildable structures and both gate sets.

---

## What I need from you

For each of the 6 proposals, mark one of:
- ✅ **Approve for backtest** — proceeds to Phase 3b (Optuna tune) and 3c (CPCV/DSR/PBO validation)
- 🔁 **Revise thesis** — give me what to change
- ❌ **Reject** — don't backtest

Bulk approval: "approve all" works. Or "approve 1, 2, 4, 6; reject 3, 5". Or "approve all but cap to 4 by trimming the highest-correlation pair."

Phase 3b/3c per approved proposal needs ~4-8 minutes of compute (coarse grid + 100-trial Optuna + CPCV folds), so 6 approved bots ≈ 30-50 min wall-clock. Manageable in this session.

Open question for tuning: which gate set should Optuna use as the FROZEN gate during 3b — Aggressive or Neutral? (Each proposal already has its gate tagged in its config; you can override that with one global instruction.)
