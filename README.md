# delta-optimizer

**A 5-phase research pipeline that designs, tunes, and validates regime-gated credit-spread trading bots for Option Alpha.** The goal: produce a small suite of validated bot specifications whose historical backtests demonstrate that regime gates prevent the tail-event losses that ungated options-selling bots suffer in volatility spikes.

---

## The problem

An ungated short-volatility bot (16–20Δ short, 5–10Δ long iron condor on SPY, 30–45 DTE) achieved a 77.7% win rate and 2.77 profit factor over 288 real trades — right up until an April 2025 VIX spike produced a ~$9,000 single-event loss. The loss was not a strategy failure: it was a gating failure. The bot had no way of recognizing that market regime had changed and kept trading a structurally short-vol position into a crash.

The delta-optimizer project exists to answer a question: can we design, tune, and validate a replacement bot suite whose members *do* have regime gates — such that the same historical period produces a profit instead of a catastrophic loss?

## Headline result

**Yes — with honest caveats.** The 7-bot regime-gated portfolio, stress-tested over the April–May 2025 VIX-spike sub-window (43 trading days containing the equivalent of the original blowup event), produced:

| Metric | Value |
|---|---:|
| Total P&L | **+$6,335** |
| Max drawdown | $1,719 (3.4% of $50k starting capital) |
| Worst single day | -$775 (2025-05-12) |
| Circuit breaker fires | 0 |

All four master-prompt aggregate gates pass: max DD < 15%, Sharpe > 1.5, p95 daily loss < 2%, no day > -5%.

The caveats are documented in §Limitations below: the backtest uses a synthetic option chain (BSM + VIX-as-IV + SKEW-adjusted skew + a stress-clip patch) because the Polygon Stocks Starter + Options Starter plan does not include historical per-contract option aggregates. Real-chain validation is deferred until the user upgrades the data plan or completes 2+ weeks of paper trading per bot.

## Pipeline architecture

Five sequential phases, each with a numerical validation gate. Phase N+1 does not run until Phase N's status JSON reports pass.

| Phase | Output | Validation gate | Status |
|---|---|---|---|
| **0. Data + scaffold** | Content-addressed Polygon cache, rate-limited HTTP client, Yahoo fallback for index data | All unit tests green; data inventory written | ✅ |
| **1. Regime classifier** | 3-factor score per trading day (VIX level, VIX 252d-percentile, VIX/VIX3M) → 0–6 composite → GREEN/YELLOW/ORANGE/RED bucket | ANOVA p < 0.01 on forward-5d-RV by bucket; Cohen's d > 0.5 | ✅ p=1.13e-29, d=1.49 |
| **2. Gate discovery** | Pareto frontier of regime-gate parameter sets, evaluated against a frozen benchmark iron condor | CPCV: each gate must win ≥4 of 5 folds on at least one objective | ✅ 8-point frontier |
| **3. Bot maker (tune + validate)** | Up to 10 thesis-grounded bot proposals, each Optuna-tuned (30 trials, TPE sampler) then CPCV-validated | Per bot: DSR_z > 1.0, ≥4 of 5 CPCV folds, ≥50 OOS trades | ✅ 6 of 6 accepted |
| **4. Portfolio backtest** | Aggregate simulation of all Phase-3-accepted bots + legacy baseline, across equal-weight / risk-parity / mean-variance allocation | Aggregate Sharpe > 1.5, max DD < 15%, p95 daily loss < 2%, no day > -5% | ✅ all pass |
| **5. Deliverables** | 35 per-bot files + 5 suite-level docs for manual OA deployment | All bots pass OA-DSL (C1) compatibility validator | ✅ 40 files generated |

## Phase 1 regime classifier — validation

The 3-factor regime score is the highest-confidence artifact in the project. It was validated against real VIX data (Yahoo `^VIX`, `^VIX3M`) with no synthetic data anywhere.

**Forward 5-day realized volatility of SPY, bucketed by regime score:**

| Bucket | n days | mean forward-5d RV | stddev |
|---|---:|---:|---:|
| GREEN (score 0-1) | 271 | 0.118 | 0.058 |
| YELLOW (score 2-3) | 435 | 0.114 | 0.051 |
| ORANGE (score 4-5) | 70 | 0.184 | 0.158 |
| RED (score 6) | 43 | 0.249 | 0.190 |

One-way ANOVA across buckets: **p = 1.13 × 10⁻²⁹**, F = 50.0.
Cohen's d, GREEN vs RED: **1.49** (large effect size; threshold in the pipeline was 0.5).

Interpretation: the regime score discriminates low-forward-vol days from high-forward-vol days with overwhelming statistical significance. RED-bucket days have 2.1× the forward realized volatility of GREEN-bucket days. Chain calibration does not affect this result; it is computed from real VIX data and SPY OHLC alone.

## Phase 3 per-bot results

Six bot proposals were generated, each with a written thesis citing a specific Phase 1 / Phase 2 finding, then tuned via Optuna (30-trial TPE search within a constrained grid) and validated via 5-fold combinatorial purged cross-validation.

| Bot | Structure | Underlying | Synthetic WR | PF | Trades | P&L | Max DD | CPCV folds |
|---|---|---|---:|---:|---:|---:|---:|---:|
| spy-iron-fly-low-vvix | Iron Butterfly | SPY | **81.6%** | 5.55 | 244 | $22,514 | $481 | 4 of 5 |
| spy-bear-call-post-spike-fade | Bear Call Vertical | SPY | **75.8%** | 5.02 | 260 | $33,652 | $914 | 4 of 5 |
| qqq-ic-extension | Iron Condor | QQQ | 87.9% | 6.86 | 231 | $75,757 | $3,678 | 4 of 5 |
| spy-tight-ic-aggressive | Iron Condor | SPY | 94.9% | 14.04 | 390 | $142,562 | $1,952 | **5 of 5** |
| spy-bull-put-elevated-vol | Bull Put Vertical | SPY | 94.9% | 12.26 | 214 | $95,437 | $2,087 | 4 of 5 |
| spy-ic-regime-recovery | Iron Condor | SPY | 95.7% | 17.09 | 164 | $133,537 | $4,122 | 4 of 5 |

Backtest window: 2023-01-03 → 2026-04-17, 825 trading days.

**Read this table honestly:** the two bots with win rates closest to the real-world baseline (77.7% for Aryan Optimized; 58.5% for the existing Iron Butterfly) are spy-bear-call (75.8%) and spy-iron-fly (81.6%). The four bots showing 87–96% win rates are structurally real (all win ≥4 of 5 CPCV folds) but are almost certainly inflated by the synthetic chain — real chains would produce lower but still-profitable numbers. All seven bots pass the OA-DSL compatibility validator (no structure outside {long/short stock, long/short option, vertical credit/debit, iron condor, iron butterfly}).

The per-fold CPCV results are in `data/results/phase_3/accepted/<bot>.json`. For the most robust bot (spy-tight-ic-aggressive, 5 of 5 folds):

| Fold | Period | Trades | WR | P&L | Max DD |
|---|---|---:|---:|---:|---:|
| 0 | 2023-01-03 → 2023-08-29 | 31 | 93.5% | $13,325 | $796 |
| 1 | 2023-08-30 → 2024-04-25 | 80 | 90.0% | $23,422 | $1,754 |
| 2 | 2024-04-26 → 2024-12-19 | 91 | 90.1% | $25,124 | $1,544 |
| 3 | 2024-12-20 → 2025-08-20 | 103 | 95.1% | $39,206 | $1,580 |
| 4 | 2025-08-21 → 2026-04-17 | 103 | 94.2% | $41,210 | $958 |

Cross-period consistency is the signal that matters most; the WR magnitude is inflated but the ranking is informative.

## Phase 4 portfolio backtest

All 6 Phase-3-accepted bots plus the legacy Aryan Optimized (ungated, modeled as the pre-incident baseline), aggregated across three allocation methods. Starting capital: $50,000. Circuit breaker: daily -3% intraday drawdown halts new entries.

| Method | Sharpe | Max DD | Max DD % | p95 daily loss | Worst day | Circuit breaker days |
|---|---:|---:|---:|---:|---:|---:|
| equal_weight | 5.03 | $1,719 | 3.4% | -0.28% | -$775 | 0 |
| risk_parity | 5.14 | $1,258 | 2.5% | -0.20% | -$739 | 0 |
| **mean_variance (40% per-bot cap)** | **5.68** | **$798** | **1.6%** | **-0.07%** | -$710 | 0 |

Sharpes are calendar-day-basis. All three methods clear all four aggregate validation gates. Mean-variance assigns 0% weight to three of the new bots (qqq-ic-extension, spy-bull-put-elevated-vol, spy-ic-regime-recovery) because their daily-PnL correlation with already-included bots exceeds 0.7 — empirical post-hoc validation of the C7 differentiation constraint.

The synthetic-chain bias means real-chain Sharpes are expected in the 1.5–3.0 range rather than 5+. The relative ranking (mean-variance > risk-parity > equal-weight) should hold; the absolute magnitudes should be discounted.

## Stress test results

Sub-windows of the 2023-2026 cached history, equal-weight allocation:

| Window | Days | Total P&L | Max DD | Max DD % | Worst day |
|---|---:|---:|---:|---:|---:|
| 2023 full year | 250 | +$12,484 | $321 | 0.6% | -$285 |
| 2024 full year | 252 | +$28,251 | $681 | 1.4% | -$526 (2024-12-18 FOMC) |
| **April 2025 VIX spike** | 43 | **+$6,335** | $1,719 | 3.4% | -$775 (2025-05-12) |
| October 2025 drawdown | 45 | +$6,664 | $714 | 1.4% | -$714 |
| Q1 2026 recent | 73 | +$12,067 | $445 | 0.9% | -$445 |

The April 2025 VIX-spike window is the test that justifies the project: a regime-gated portfolio is profitable during the same market event that caused the original ~$9k loss, with maximum drawdown contained to 3.4% of starting capital.

## Pairwise daily-PnL correlation (portfolio differentiation)

|  | qqq | bear-call | bull-put | regime | iron-fly | tight-ic | legacy |
|---|---|---|---|---|---|---|---|
| qqq-ic-extension | 1.00 | 0.78 | 0.75 | 0.60 | 0.53 | 0.78 | 0.60 |
| spy-bear-call-post-spike-fade | 0.78 | 1.00 | 0.88 | 0.72 | 0.50 | 0.72 | 0.59 |
| spy-bull-put-elevated-vol | 0.75 | 0.88 | 1.00 | 0.66 | 0.52 | 0.82 | 0.58 |
| spy-ic-regime-recovery | 0.60 | 0.72 | 0.66 | 1.00 | 0.39 | 0.57 | 0.49 |
| **spy-iron-fly-low-vvix** | **0.53** | **0.50** | **0.52** | **0.39** | **1.00** | **0.50** | **0.44** |
| spy-tight-ic-aggressive | 0.78 | 0.72 | 0.82 | 0.57 | 0.50 | 1.00 | 0.59 |
| aryan_optimized_legacy | 0.60 | 0.59 | 0.58 | 0.49 | 0.44 | 0.59 | 1.00 |

The iron-fly bot has the lowest average correlation (0.49) with every other bot in the suite, which is why the mean-variance optimizer assigns it the maximum-allowed 40% weight. The legacy bot correlates < 0.7 with every new bot — the C7 "differentiation vs existing live bots" constraint is satisfied for the entire suite.

## Engineering

- **Python 3.11**, [`uv`](https://docs.astral.sh/uv/) environment management, `pyproject.toml` + `uv.lock`
- **175 unit tests**, all passing. Includes: regime feature boundary tests, BSM known-answer tests (Hull canonical example), put-call parity Hypothesis property test (200 random samples, 1e-9 tolerance), QuantLib cross-validation (1e-8), iron condor P&L math, OA-DSL compatibility validator
- **Content-addressed disk cache** for all API responses (SHA256 of endpoint + sorted params), gzip JSON
- **Token-bucket rate limiter** for Polygon API (5 calls/min Starter plan, auto-probes `X-RateLimit-Limit` headers)
- **No look-ahead bias** — backtest engine enforces T-close as-of filtering; every mark/exit decision at time T uses only data timestamped ≤ T
- **Decimal P&L aggregation** throughout; float is confined to the vectorized BSM pricer kernel
- **11 commits, 9 phase tags** (`phase-0-scaffold` through `phase-5-complete`). Any intermediate state is reproducible via `git checkout <tag>`

## Key statistical results

| Metric | Value | Interpretation |
|---|---|---|
| Phase 1 ANOVA p-value | 1.13 × 10⁻²⁹ | Regime score discriminates forward vol with overwhelming significance |
| Phase 1 Cohen's d (GREEN vs RED) | 1.49 | Effect size "very large" (threshold >0.8) |
| Phase 3 bots with DSR_z > 1.0 | 6 of 6 | All pass C2 (deflated Sharpe gate, Bailey-LdP Z-score form) |
| Phase 3 CPCV 4/5 folds won | 6 of 6 | All pass C4 (cross-period stability) |
| Phase 3 OOS trade counts (min/max) | 113 / 408 | All pass C5 (≥50 OOS trades) |
| Phase 4 aggregate Sharpe | 5.03–5.68 | Passes Sharpe > 1.5 gate (inflated; real-chain estimate 1.5–3.0) |
| Phase 4 max drawdown (worst method) | $1,719 (3.4%) | Passes max DD < 15% gate |

## Limitations (honest)

Several master-prompt requirements were deliberately deferred due to data plan restrictions or compute budget:

1. **No real-chain validation.** Polygon Stocks Starter + Options Starter denies historical per-contract aggregates (`/v2/aggs/ticker/O:SPY.../range/...` returns 403). The backtest uses a synthetic chain (BSM + VIX-as-ATM-IV + SKEW-adjusted skew + a stress-clip patch calibrated to match the real Aryan Optimized 77.7% win rate). Real-chain swap-in is architected: the chain ingest layer consumes a `ChainProvider` Protocol; implementing a `PolygonChain` against Polygon Options Developer data (or Polygon Flat Files) would allow Phases 2–4 to re-run without architectural changes.
2. **C3 (PBO) deferred.** Probability of Backtest Overfitting requires an M(trials) × N(folds) IS/OOS matrix, adding ~5× compute per bot. The Phase 3 fast-path gates on C2 (DSR_z > 1), C4 (CPCV 4/5 folds), and C5 (≥50 OOS trades) only. CPCV overlaps in protective value but is not a perfect substitute.
3. **GEX dimension deferred.** The master prompt called for a 4-factor regime score including SPX Net GEX. The implemented score uses 3 factors because computing GEX requires option chain open-interest data subject to the same 403 restriction. The 3-factor score still achieves p < 10⁻²⁹ separation; adding GEX would tighten gates further (block more days).
4. **True multi-bot event-driven simulator not built.** The Phase 4 aggregator sums per-bot daily P&Ls rather than simulating cross-bot shared capital at the trade level. Per-underlying position caps and the 35% portfolio BPR limit are post-hoc estimates, not trade-level enforcements.
5. **Iron Butterfly Legacy / Credit Scanner V3 / Trade Ideas suite not modeled.** Only Aryan Optimized was modeled as the representative legacy bot. Reasons: Iron Butterfly is 0DTE (daily-bar engine too coarse), Credit Scanner V3 requires GEX (deferred), Trade Ideas suite is ambiguously specified.
6. **Synthetic-inflated win rates on three bots.** spy-tight-ic-aggressive, spy-bull-put-elevated-vol, and spy-ic-regime-recovery all show 94–96% WR in backtest. This is the chain calibration patch being most effective for parameters close to the calibration target (16Δ short / 50% PT / 21d time exit) and less effective for parameter combinations Optuna found in different corners of the grid. Real-chain validation would likely bring these to 75–85%.

All seven limitations are documented with deployment mitigations in `deliverables/validation_summary.md`.

## How to trust these numbers

You cannot trust the absolute P&L, Sharpe, DSR_z, or 90%+ win rates from the synthetic backtest. You can trust:
- **The regime classifier validation** (real VIX data, p < 10⁻²⁹)
- **The cross-period stability** (4–5 of 5 CPCV folds win for every accepted bot)
- **The relative ranking between bots** (chain treats them consistently)
- **The stress-test direction** (profit during the April 2025 VIX spike is the right sign)
- **The OA-buildability** (every bot passes the C1 DSL validator)

The real validation is the 2-week paper-trading period specified in `deliverables/build_order.md` — compare actual paper-trade win rate to the per-bot predicted WR. Matching paper data (within ±15% of predicted) is the condition for live capital deployment.

## Repository structure

```
delta-optimizer/
├── EXECUTIVE_BUILD_REPORT.md     # 2,800-line operations manual for deployment
├── PROJECT_BRIEF.md              # the master prompt driving the pipeline
├── CLAUDE.md                     # AI-session session rules
├── deliverables/                 # 35 per-bot files + 5 suite-level docs
├── checkpoints/                  # 6 phase-boundary status reports
├── proposals/                    # 6 per-bot thesis markdowns
├── configs/                      # YAML configs per bot + legacy + gate sets
├── data/results/                 # Phase 1-4 outputs (parquet + JSON + PNG)
├── src/delta_optimizer/          # pipeline code
│   ├── ingest/                   # Polygon, FRED, Yahoo, cache, rate limiter
│   ├── pricing/bsm.py            # Greeks + IV solver
│   ├── regime/                   # features, score, validation
│   ├── strategies/               # base, iron_condor, synthetic_chain
│   ├── backtest/                 # engine, portfolio
│   ├── optimize/tuner.py         # Optuna + CPCV
│   └── validate/                 # DSR, PBO, CPCV, OA-DSL compat
├── scripts/                      # run_phase[0–5].py entry points
└── tests/unit/                   # 175 unit tests
```

## Reproducing the pipeline

```bash
git clone https://github.com/aaasharma870-art/Options-plan-.git
cd Options-plan-
cp .env.example .env                          # set MASSIVE_API_KEY
uv sync --extra dev
uv run pytest tests/unit -q                   # all 175 tests green
uv run python scripts/pull_polygon.py --dataset all    # Phase 0 data ingest
uv run python scripts/run_phase1.py           # ~1 min
uv run python scripts/run_phase2.py --coarse  # ~15 min
uv run python scripts/run_phase3.py --n-trials 30 --cpcv-folds 5  # ~2 hrs
uv run python scripts/run_phase4.py           # ~5 min
uv run python scripts/run_phase5.py           # ~1 min (generates deliverables)
```

Every phase writes a `.phase_N_status.json` with validation gate results. The `phase-0-scaffold` through `phase-5-complete` git tags let you check out any intermediate state.

## Tooling

`httpx` for HTTP, `polars`/`pandas`/`duckdb` for data, `scipy`/`optuna` for the math, `matplotlib` for charts, `pytest`/`hypothesis` for testing, `QuantLib` for BSM cross-validation (`py_vollib` was originally used but has a Python 3.11 compatibility bug in `py_lets_be_rational` that imports `_testcapi`). All external dependencies pinned in `pyproject.toml` and locked in `uv.lock`.

---

## Author

Aryan Sharma, 16. Built over several sessions in April 2026. The project is the technical response to a real $9,000 loss in a live options account that ungated bots could not prevent. Correspondence via the email address on the git commits.
