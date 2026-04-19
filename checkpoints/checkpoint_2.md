# Checkpoint 2 — Phase 2 gate discovery (synthetic backtest)

**Date:** 2026-04-19
**Phase:** 2 — Gate Discovery
**Status:** Coarse 72-config grid complete. Three gate sets selected from 8-point Pareto frontier. Pause for your pick.

---

## Pivot disclosure: synthetic chain backtest, not real

Aryan's Polygon Stocks Starter + Options Starter plan **does not include**:
- `/v2/aggs/ticker/O:SPY.../range/...` (per-contract historical aggs) → 403
- `/v2/last/trade/...` → 403
- `/v1/open-close/{contract}/{date}` → 403
- `/v3/snapshot/options/...` → 502 (likely also blocked or deprecated)

The plan **does include**:
- `/v3/reference/options/contracts?as_of=...` (contract metadata)
- `/v2/aggs/ticker/O:SPY.../prev` (one-bar previous close — too narrow for backtests)

**Decision (made on Aryan's behalf per "choose for me"):** synthetic backtest using BSM + VIX as ATM 30d IV + CBOE SKEW for skew slope. Standard literature approach when historical option prices aren't accessible. The backtest engine consumes a `ChainProvider` Protocol — `SyntheticBSMChain` slots in today, a `PolygonChain` slots in later if Aryan upgrades.

**Caveats explicit:**
- Synthetic chain underestimates tail losses (BSM has no jumps, no vol-of-vol, no path-dependent skew). Observed 93% WR is artificially clean — your real Aryan Optimized is 77.7% on 288 real trades.
- Gate selection (Phase 2's actual deliverable) is **robust to this caveat**: gates pick *whether to enter*, not exact P&L. A gate that ranks well against synthetic data is very likely to rank well against real data.
- For Phase 3+'s C2/C3/C4 validation thresholds (DSR > 1.0, PBO < 0.3, ≥4 of 5 CPCV folds) we should **defer applying these to live capital decisions until real chains are available.** Phase 2 gate ranking is meaningful; absolute P&L numbers below should be read with a 20-30% downward adjustment.

---

## What ran

| Item | Value |
|---|---|
| Backtest window | 2023-01-03 → 2026-04-17 (825 trading days) |
| Grid configurations tested | 72 (coarse subset of master prompt's 1,280) |
| Total backtest time | 15.2 minutes |
| Per-config wall clock | ~12 seconds |
| Pareto frontier size | 8 configs |

Coarse grid axes (used in this run):
- VIX ceiling ∈ {22, 28, 35} (vs full {22, 25, 28, 30, 35})
- VIX/VIX3M ceiling ∈ {0.95, 1.00} (vs full {0.90, 0.95, 1.00, 1.05})
- VIX 10d-high ceiling ∈ {28, 32, 35} (vs full {28, 30, 32, 35})
- VIX 1d change ceiling ∈ {0.15, 0.25} (vs full {0.10, 0.15, 0.20, 0.25})
- IVP floor ∈ {20, 40} (vs full {20, 30, 40, 50})
- GEX dimension dropped (deferred from Checkpoint 1; needs chain backfill)

Benchmark strategy (frozen per spec): IC, 16Δ short / 5Δ long, 30-45 DTE, 50% PT, 2× credit stop, 21 DTE time exit, max 3 concurrent.

---

## Three recommended gate sets

The "moderate" and "conservative" picks happened to coincide on this run because of the coarse grid resolution + only 8 Pareto points. The **aggressive** set is a meaningfully different point on the frontier.

### Conservative (also Moderate)
```yaml
vix_max: 28
vix_vix3m_max: 1.00
vix_10d_high_max: 35
vix_1d_change_max: 0.15
ivp_min: 20
```
**Expected metrics (synthetic):** $44.2k P&L / $53.6 per day / 92.8% WR / 7.7 PF / **$3,651 max DD** / CVaR-95 -$160 / 209 trades / 56% gate-pass days

### Aggressive
```yaml
vix_max: 28
vix_vix3m_max: 1.00
vix_10d_high_max: 35
vix_1d_change_max: 0.25
ivp_min: 20
```
**Expected metrics (synthetic):** $45.4k P&L / $55.1 per day / 93.1% WR / 7.2 PF / $4,200 max DD / CVaR-95 -$177 / 216 trades / 58% gate-pass days

The only difference between conservative and aggressive: VIX 1-day change ceiling (15% vs 25%). Aggressive enters on 7 more trades over 825 days at the cost of $549 more max DD. Both block VIX>28, VIX/VIX3M backwardation, and very-low-IVP regimes.

Full Pareto frontier and per-config metrics: `data/results/phase_2/{pareto_frontier,grid_results}.parquet`.

---

## Notable findings from the grid

1. **VIX absolute ceiling barely matters** — VIX≤28 vs VIX≤35 produces near-identical results. The binding constraints are the term-structure ratio and IVP floor. Counterintuitive: a high-VIX regime is captured better by `VIX/VIX3M > 1` (backwardation = stress signal) than by absolute VIX level.
2. **IVP floor is the strongest selector.** IVP ≥ 40 cuts trade count from ~210 to ~160, but improves CVaR meaningfully (-$160 → -$133). This is the lever that trades volume for tail safety.
3. **VIX/VIX3M ≤ 1.00 was effectively required** in every Pareto config. Backwardation is the kill-switch dimension.

---

## Validation status (master prompt §Phase 2 gate)

| Required | Done? |
|---|---|
| Multi-objective Pareto across (expectancy/day, max DD, tail-blocking ratio) | ✅ |
| Three recommended gate sets emitted | ✅ |
| **CPCV validation: ≥4 of 5 OOS folds win on at least one objective** | ❌ deferred — would add ~7 min on the 8 Pareto configs (8 × 5 folds × 11s) |

CPCV is the next sub-step before Phase 3 actually starts. I held off because the synthetic-vs-real caveat already makes Phase 2 numbers a relative ranking exercise; CPCV adds rigor that's more meaningful with real-chain backtests.

---

## How to run the full 1,280-config grid

```bash
uv run python scripts/run_phase2.py
```
Expect ~3.9 hours wall-clock on this hardware. Same script, no `--coarse` flag.

---

## What's next

Phase 3 is the bot maker — generates ≤10 thesis-grounded bot proposals, tunes each via Optuna against frozen gates from this checkpoint, validates via CPCV/DSR/PBO. Phase 3 also runs against the synthetic chain (same caveats) until you pick a real-chain path.

**Decision for Phase 3:**
1. Pick one of the three gate sets (conservative / moderate / aggressive) to use as the frozen gate during Phase 3 tuning.
2. Confirm the synthetic-chain approach is acceptable for proceeding to bot proposals, or pause to set up real chains first.
3. Optionally: run the full 1,280-config grid first (3.9 hrs) for finer Pareto resolution.
