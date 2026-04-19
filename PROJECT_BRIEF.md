# Claude Code Master Prompt: delta-optimizer Bot Maker

**Instructions for Aryan:** Paste this entire document into Claude Code as your first message. Claude Code will read it, acknowledge, and begin Phase 0. You approve phase transitions (4 checkpoints total); everything else runs autonomously.

---

## YOUR MISSION

You are building an autonomous bot research system called `delta-optimizer`. Its purpose is to **invent, tune, and validate credit-spread trading bots that I will manually build in Option Alpha (OA)**. You are a bot maker.

For each bot you produce, you will: generate a written thesis grounded in specific regime findings, tune its parameters using Optuna Bayesian optimization, validate it with Combinatorial Purged Cross-Validation (CPCV), compute its Deflated Sharpe Ratio, and output exact OA build specifications that I type into OA's UI. No API automation, no live trading — OA has no config API and you must not attempt to automate it.

The final deliverable is a set of 4–8 validated bot specs organized by regime, complete with OA decision-tree build instructions, gate settings, delta targets, DTE windows, exit rules, position sizing, and per-bot theses.

---

## CONTEXT YOU INHERIT

I am Aryan, a 16-year-old quantitative trader. My live OA bot suite includes:

- **Aryan Optimized** — iron condor, 288 trades, 77.7% WR, 2.77 PF, 7.27 Sharpe (raw — likely inflated), .28-.32 short / .05-.10 long delta, 30-45 DTE
- **Iron Butterfly** — 0DTE, .50/.10 delta, $252/trade, 58.5% WR
- **Credit Scanner V3** — 0DTE GEX-routed SPY
- **Trade Ideas Scanner V1 suite** — bull put, bear call, iron fly

Two weeks ago I lost $9k in a VIX spike because my bots had no hard regime gates. Research (see `research/delta_optimization_report.md` if you find it in the repo) established four facts that constrain this entire project:

1. The blowup was a gate failure, not a delta failure. The 4-factor regime score (VIX level, IV Percentile, VIX/VIX3M, SPX GEX) is the highest-value artifact you produce — more important than any delta.
2. My 7.27 Sharpe is a short-vol illusion. After Deflated Sharpe correction, realistic Sharpe is 1.5-3.0. Do not trust raw Sharpe for production decisions.
3. Delta literature converges narrow (16-20Δ short / 5Δ long at 30-45 DTE) but dispersion inside that band comes from regime, not the delta itself.
4. OA platform constraints are real — no Brain Bot, no webhook parameterization, position caps per-bot only, native GEX is experimental.

The scaffold for this repo was partially built in a prior session. Check if `PROJECT_BRIEF.md`, `CLAUDE.md`, `src/delta_optimizer/`, `pyproject.toml`, and `.env.example` exist. If yes, extend them. If no, build from scratch per the architecture below.

---

## HARD CONSTRAINTS — NON-NEGOTIABLE

These disqualify any output that violates them. Enforce in code, not just intent.

**C1. OA buildability.** Every bot you produce must be fully expressible in OA's decision-tree DSL:
- Allowed structures: long/short stock, long/short single option, vertical credit or debit spread, iron condor, iron butterfly
- Forbidden: calendars, diagonals, strangles, straddles, ratio spreads, any multi-expiry structure
- Allowed entry filters: delta, DTE, IV Rank, IV Percentile, VIX level, VIX/VIX3M ratio, VIX 10-day high, VIX velocity, RSI, MACD, EMA, ADX, Bollinger, Keltner, CCI, net GEX, max-GEX strikes, earnings calendar, FOMC/CPI/NFP calendar, ORB (for 10 supported tickers)
- Allowed exits: profit target %, stop loss % or $, trailing stop (trigger + pullback), DTE exit, ITM close, PDT 1-day wait
- Max 5 scanner automations per bot. Max 25 symbols per bot (supercharged). Max 25 concurrent positions per bot.

If a bot concept requires anything not in the allowed list, discard it. Do not propose "enhancements" that require non-OA features.

**C2. Deflated Sharpe Ratio > 1.0 for every accepted bot.** Use Bailey & López de Prado 2014 formulation. Correct for (a) number of parameter configurations tested, (b) return non-normality (skew, kurtosis). A bot with DSR < 1.0 is rejected no matter how good the raw Sharpe looks.

**C3. Probability of Backtest Overfitting (PBO) < 0.3** per bot, via Combinatorial Symmetric Cross-Validation.

**C4. CPCV fold stability.** Each accepted bot must win ≥4 of 5 out-of-sample CPCV folds on DSR. Stable region > peak. If config A has higher mean DSR but loses 2 folds, and config B has lower mean DSR but wins 5 folds, ship config B.

**C5. Minimum 50 trades in out-of-sample test folds.** Below that threshold, validation is not credible.

**C6. Written thesis before backtest.** Every bot proposal starts as a markdown file at `proposals/YYYY-MM-DD-<name>.md` containing:
1. The specific regime finding or structural inefficiency it exploits (cite Phase 1-2 results)
2. Why this structure captures that edge (the economic mechanism)
3. Predicted performance ranges (WR, PF, trade frequency)
4. Failure mode — when will this bot lose money, what's the drawdown scenario
5. Differentiation — how is this different from existing bots

The backtester refuses to run against a config whose thesis file doesn't exist. Enforce this structurally.

**C7. Differentiation.** Any new bot with >0.7 pairwise daily-PnL correlation against an existing bot (Aryan Optimized, Iron Butterfly, Credit Scanner V3, Trade Ideas suite) is rejected. It does not add edge; it adds capital consumption.

**C8. No look-ahead bias.** Entries fill at T+1 open or at T close with explicit as-of filter. Write a synthetic-data test where any look-ahead produces a distinguishable PnL diff. Run it every CI cycle.

**C9. Decimal P&L.** All money in `Decimal`, never `float`. Float is allowed only inside vectorized Black-Scholes kernels. Aggregations use Decimal.

**C10. Single-name earnings exclusion.** Any single-name entry with expiration on/after next earnings date is rejected by the chain builder, not the backtester. Structural, not post-hoc.

**C11. Point-in-time data.** Universe for single names is S&P 500 constituents as-of each trade date, not today's list. Delisted symbols remain in the universe up to delisting.

**C12. Max 10 bot proposals total across the project.** Quality over quantity. If you exhaust 10 slots without producing 4+ accepted bots, stop and report back rather than invent more.

---

## DATA INFRASTRUCTURE

**Polygon.io plans available to you:** Options Starter + Stocks Starter. At session start, query Polygon's rate limit documentation to determine current limits (these changed in 2024 — do not assume 5/min). Implement a token-bucket rate limiter with the actual current limits plus 20% safety margin.

**Required data pulls:**

| Source | Data | Tickers | Date range |
|---|---|---|---|
| Polygon Stocks | EOD OHLC | SPY, QQQ, IWM, AAPL, MSFT, NVDA, META, GOOGL, AMZN, TSLA | 2022-01-01 to yesterday |
| Polygon Options | EOD chain snapshots, 0-60 DTE | Same 10 tickers | 2022-01-01 to yesterday |
| Polygon Indices | EOD close | VIX, VIX3M, VVIX, SKEW | 2022-01-01 to yesterday |
| FRED | 13-week T-bill rate | DTB3 | 2022-01-01 to yesterday |
| Polygon reference | Earnings dates | 7 single names | 2022-01-01 to yesterday |

**Caching:** disk cache every response in `data/raw/` keyed by SHA256 of (endpoint, params_sorted_json). Content-hashed, idempotent. Never re-pull cached data.

**Storage:** partition parquet files by date and underlying in `data/lake/`. Use DuckDB for queries during backtests — fits in memory, no server.

**Install and configure Polygon MCP** if available (`polygon-io/mcp_polygon` on GitHub). Grounds API calls against real method names, prevents hallucinated endpoints.

**Compute Greeks locally.** Polygon Options Starter does not return Greeks. Use `py_vollib` or `quantlib-python`. Every Greek needs a hand-computed unit test (e.g., SPY 420C, spot 425, DTE 30, IV 15%, r 5%, q 0 → delta ≈ 0.66). Never `approx(self_output)`. Put-call parity as a Hypothesis property test for every pricer.

---

## EXECUTION PROTOCOL

You run phases autonomously between 4 checkpoints. At each checkpoint, write a summary to `checkpoints/checkpoint_<N>.md` and wait for explicit "proceed" or "revise" from me.

**Autonomous mode between checkpoints:**
- Plan before coding using Plan Mode (Shift+Tab)
- Commit after every green test with descriptive messages
- Run full regression tests before phase transitions
- If stuck for >30 minutes on a single issue, write a diagnostic note and continue with the next task

**Checkpoint triggers:**

| # | After | Deliverable | I decide |
|---|---|---|---|
| 1 | Phase 1 complete | Regime score chart + ANOVA stats | Proceed or refine thresholds |
| 2 | Phase 2 complete | Pareto frontier of gate sets | Pick conservative/moderate/aggressive |
| 3 | Phase 3 bot proposals drafted (theses only, no backtests yet) | Review of all proposed theses | Approve which to backtest |
| 4 | Phase 5 complete | Full suite with allocation weights | Approve for manual OA build |

**Autonomous session posture:** you default to Sonnet. Switch to Opus only when I instruct or when Phase 3 thesis generation requires sustained reasoning. Monitor `/cost` per session.

**Context management:** run `/compact Keep current phase, file being edited, last test result. Drop earlier phase detail.` whenever context hits 60%. Do not wait for auto-compact.

---

## PHASE 0 — SCAFFOLD AND DATA

**Duration target:** 1 day of work + overnight data pulls.

Verify or create the repo skeleton:

```
delta-optimizer/
├── PROJECT_BRIEF.md
├── CLAUDE.md
├── pyproject.toml (uv)
├── .env.example
├── src/delta_optimizer/
│   ├── ingest/        # polygon_client, fred_client, cache
│   ├── pricing/       # bsm, greeks, iv_solver
│   ├── regime/        # vix_regime, iv_percentile, gex, composite_score
│   ├── strategies/    # ic, if, bull_put, bear_call, base
│   ├── backtest/      # engine, position, portfolio
│   ├── optimize/      # grid, optuna_tune, cpcv, dsr, pbo
│   ├── validate/      # gate_checks, differentiation, oa_compat
│   └── report/        # oa_build_spec, equity_curves, stress_tests
├── proposals/         # thesis markdown files
├── configs/           # bot configs per phase
├── data/{raw,lake,results,checkpoints}/
├── tests/{unit,property,regression,golden/}
└── scripts/           # CLI entry points
```

Install deps via uv: `polygon-api-client`, `polars`, `pandas`, `duckdb`, `pyarrow`, `py_vollib`, `quantlib`, `scipy`, `numpy`, `optuna`, `skfolio`, `arch`, `hypothesis`, `pytest`, `pytest-cov`, `ruff`, `mypy`, `rich`, `typer`, `python-dotenv`, `fredapi`, `tqdm`.

Run Polygon data pulls overnight. Report total size, date coverage, any gaps. Write `checkpoints/checkpoint_0_data_ready.md` when complete.

---

## PHASE 1 — REGIME CLASSIFIER

**Duration target:** 3-5 days.

Build the 4-factor regime score and validate it predicts forward vol.

**Features per trading day:**
- VIX level, VIX 10-day high, VIX 1-day % change
- IV Percentile per underlying (252-day window on ATM 30-DTE IV)
- VIX/VIX3M ratio (contango/backwardation signal)
- Approximate SPX Net GEX (compute from SPY chain OI × BSM gamma; document the approximation with a comment noting this is a proxy for true dealer GEX)
- Realized Vol 20-day close-to-close, annualized
- Volatility Risk Premium = ATM IV − RV_20d
- SKEW index level

**Composite score table (starting thresholds — validate in Phase 1 gate):**

| Dimension | 0 (Green) | +1 (Yellow) | +2 (Red) |
|---|---|---|---|
| VIX level | <17 | 17-22 | >22 |
| IV Percentile | 50-80 | 30-50 or 80-90 | <30 or >90 |
| VIX/VIX3M | <0.95 | 0.95-1.00 | >1.00 |
| SPX GEX | >+1B | −1B to +1B | <−1B |

Composite 0-8. Buckets: 0-1 GREEN, 2-3 YELLOW, 4-5 ORANGE, 6+ RED.

**Phase 1 validation gate (must pass to proceed):**

Compute forward metrics per day: realized vol over next 5 trading days, max intraday drawdown of SPY over next 5 days.

Run one-way ANOVA of forward RV bucketed by regime score. Require p < 0.01 between GREEN vs RED. Compute Cohen's d; require d > 0.5.

If ANOVA fails, iterate on thresholds (not the score construction) within ±3 units of starting values. If still fails after 3 iterations, stop and write diagnostic report. Do not proceed to Phase 2 with a broken regime score.

Write `data/results/.phase_1_status.json` with pass/fail, ANOVA stats, Cohen's d, final thresholds. Render regime-score-over-time chart to `data/results/phase_1/regime_timeline.png`.

**Checkpoint 1:** write `checkpoints/checkpoint_1.md` with regime chart, separation stats, and recommended next step. Wait for my approval.

---

## PHASE 2 — GATE DISCOVERY

**Duration target:** 3-5 days including compute.

Find gate threshold configurations that maximize expectancy-per-day while eliminating tail events.

**Benchmark strategy (fixed for gate testing):** iron condor, 16Δ short / 5Δ long, 30-45 DTE, 50% profit target, 2× credit stop, 21 DTE time exit, 1 contract, max 3 concurrent. Do not tune this — it's the ruler.

**Gate parameter grid:**
- VIX ceiling: {22, 25, 28, 30, 35}
- VIX/VIX3M ceiling: {0.90, 0.95, 1.00, 1.05}
- VIX 10-day high ceiling: {28, 30, 32, 35}
- VIX 1-day velocity ceiling: {10%, 15%, 20%, 25%}
- IVP floor: {20, 30, 40, 50}
- Require positive SPX GEX: {true, false}

That's 5×4×4×4×4×2 = 2,560 configurations. For each, run the benchmark across 2022-present on gate-passed days. Record: total trades, WR, expectancy/trade, expectancy/day (blocked days count as $0), worst 5 trading days, max DD, CVaR95.

**Multi-objective Pareto:**
1. Maximize expectancy/day
2. Minimize max DD
3. Maximize ratio of (P&L blocked on bottom-5% days) / (P&L blocked on top-50% days)

Report Pareto frontier. Validate each frontier point via CPCV — require ≥4 of 5 OOS fold wins on at least one objective.

**Output three recommended gate sets:**
- **Conservative:** blocks most days, max DD minimized
- **Moderate:** balanced expectancy/risk
- **Aggressive:** highest expectancy, larger tail risk

Write to `configs/gate_sets.yaml`. Write `data/results/.phase_2_status.json`.

**Checkpoint 2:** write `checkpoints/checkpoint_2.md` with Pareto chart and the three recommended sets. I pick which set downstream phases use.

---

## PHASE 3 — THE BOT MAKER (CORE PHASE)

**Duration target:** 2-3 weeks. This is the centerpiece.

You produce up to 10 bot proposals. Each goes through three sub-phases: thesis → tune → validate. Proposals that fail validation are archived but do not count against the 10-slot cap.

### 3a. Thesis generation

You propose bots by inspecting Phase 1-2 outputs for **regime-conditional gaps** in the existing bot suite. A gap = a regime + structure combination where no existing bot trades, or trades poorly.

**Sources of bot ideas (in priority order):**

1. **Fill regime gaps in existing suite.** If Aryan Optimized and Iron Butterfly both require YELLOW+ regimes but underperform in GREEN, propose a GREEN-specific iron condor with parameters suited to compressed-vol tape.
2. **Structural variants with timing edge.** Example: "Iron condor that only enters at 10:30 AM on days where GEX > +500M and VIX < 15." Timing filters count as regime conditioning.
3. **Asymmetric structures.** Skewed-delta iron condors based on SPX GEX above/below ratio (short call closer to ATM when GEX concentrated above; short put closer when concentrated below).
4. **Underlying class extensions.** If Phase 3 finds a SPY config works, test the same config on QQQ and IWM with class-appropriate delta adjustments.
5. **Regime-transition bots.** Enter on the day regime flips GREEN after ORANGE/RED; close on first return to YELLOW.

**Forbidden idea sources:**
- Novel structures outside OA-buildable list (C1)
- Machine-learned features that weren't validated in Phase 1-2
- Strategies that tune >3 new parameters beyond the Phase 3 baseline
- "Backtest showed this works" with no pre-stated economic hypothesis

For each idea, draft `proposals/YYYY-MM-DD-<slug>.md` with the 5 required sections (regime finding, mechanism, predictions, failure mode, differentiation). **Do not backtest yet.**

**Checkpoint 3:** when you have 6-10 thesis drafts, write `checkpoints/checkpoint_3.md` listing all proposals. I review and approve which proceed to 3b.

### 3b. Optuna tuning

For each approved proposal:

**Coarse grid on approved gate set (from Checkpoint 2):**
- short_delta ∈ {8, 12, 16, 20, 25, 30}
- long_delta ∈ {3, 5, 8, 12}
- DTE window ∈ {(0,2), (7,14), (14,21), (21,30), (30,45), (45,60)}
- profit_target_pct ∈ {25, 35, 50, 75}
- stop_loss (× credit) ∈ {1.0, 1.5, 2.0, 3.0}
- time_exit_DTE ∈ {0, 7, 14, 21}

Filter invalid combos (long_delta ≥ short_delta; 0DTE with time_exit > 0; long_delta < 3 on single names; etc.).

**Optuna refinement:** take top 5% of coarse grid by DSR. Run Optuna with 100 trials in a tighter neighborhood. Objective: DSR, not raw Sharpe. Use TPE sampler with median pruner.

**Underlying classes (enforce parameter shifts):**
- Class A (SPY, QQQ, IWM): base parameters
- Class B (AAPL, MSFT, GOOGL, AMZN): short_delta shifted -3Δ
- Class C (NVDA, META, TSLA): short_delta shifted -5Δ, fixed-$ wings only, IVR ≥ 60 required

### 3c. Validation

Every tuned config must pass:

1. **DSR > 1.0** (corrected for number of configs tested: ~2,000 coarse + 100 Optuna = use N=2,100)
2. **PBO < 0.3** via CSCV
3. **≥4 of 5 CPCV folds won** on DSR with purge + embargo
4. **≥50 OOS trades** across folds combined
5. **Correlation < 0.7** vs existing bots (Aryan Optimized, Iron Butterfly, Credit Scanner V3, Trade Ideas suite)
6. **Drawdown ceiling:** max DD < 2× expected daily P&L × 30 (sanity check)
7. **OA compat:** generate the OA decision-tree DSL representation and assert it parses against the OA capability list (C1)

If all pass → write to `data/results/phase_3/accepted/<bot_name>.yaml` + `<bot_name>_report.md`.
If any fail → archive to `data/results/phase_3/rejected/` with explicit reject reason.

**Stable region preference:** among candidates that pass all 7 gates, select the one with lowest fold-to-fold Sharpe variance, then tie-break on minimum max DD. Do not select the peak IS Sharpe.

Target: 4-6 accepted bots by end of Phase 3. If you accept fewer than 3 from the 10 proposal slots, stop and write a diagnostic report rather than invent more.

---

## PHASE 4 — PORTFOLIO BACKTEST

**Duration target:** 1 week.

Simulate running all accepted bots (Phase 3) plus existing bots (Aryan Optimized, Iron Butterfly, Credit Scanner V3, Trade Ideas suite) together.

**Portfolio constraints:**
- Per-bot position cap per each bot's config
- Per-underlying total position cap: 4 max
- Portfolio max 35% BPR at any time
- Daily −3% drawdown circuit breaker halts all new entries for the rest of the day
- Starting capital $50k
- Margin: 1.5× BPR on credit spreads

**Simulation:** event-driven daily bar. Each morning, check which bots' gates pass. Allocate capital across passing bots by weight. Open positions per each bot's rules. Each afternoon, mark all positions to market, check exits. Aggregate daily P&L, running DD, BPR utilization, inter-bot correlation.

**Allocation methods (compare all three):**
1. Equal weight
2. Risk parity (equal risk contribution)
3. Mean-variance (max Sharpe, 40% per-bot cap)

**Aggregate validation gates:**
- Max DD < 15% of starting capital
- Sharpe > 1.5 calendar-day basis
- 95th percentile daily loss < 2% capital
- No single day > 5% loss across the full backtest

**Stress tests (run separately, report distinct results):**
- 2022 bear market (Jan-Oct 2022)
- Feb 2018 Volmageddon
- March 2020 COVID
- April 2024 recent VIX spike
- The specific days around the $9k blowup event

If any stress test shows unacceptable loss with the selected gate set (from Checkpoint 2), revert to Phase 2 Checkpoint and pick a more conservative set.

---

## PHASE 5 — OA BUILD SPECS

**Duration target:** 2-3 days.

Produce the manual-build deliverables.

**Per accepted bot, generate `deliverables/bots/<bot_name>/`:**

1. `README.md` — bot summary, thesis, expected performance, regime it trades
2. `oa_build_guide.md` — step-by-step OA UI instructions with exact field values:
   - Bot name, underlyings, allocation limit, position limits, scan speed
   - Each automation: trigger, decision tree with every gate and entry filter, position criteria, order settings, exit rules
   - Screenshots placeholders (I fill these as I build)
3. `config.yaml` — machine-readable config for regeneration
4. `performance.md` — DSR, PBO, CPCV fold distribution, max DD, Sharpe, WR, PF, trade frequency
5. `kill_switches.md` — conditions under which to pause this specific bot

**Suite-level deliverables `deliverables/`:**

1. `suite_summary.md` — all bots at a glance, allocation weights, aggregate metrics
2. `regime_monitor.md` — how to check the 4-factor regime score daily without re-running the pipeline (specific Polygon endpoints, TradingView/Barchart URLs, formula reference)
3. `portfolio_kill_switches.md` — conditions that pause the entire suite (VIX backwardation > 1.05, account DD > 5%, regime RED 3 consecutive days)
4. `validation_summary.md` — honest reporting of DSR, PBO, CPCV distributions, stress test results, plus explicit caveats about what the backtest cannot capture
5. `build_order.md` — sequence to build bots in (paper first, live after 2 weeks of successful paper validation)

**Checkpoint 4:** write `checkpoints/checkpoint_4.md` with the full deliverable package. I review before starting manual OA builds.

---

## BOT SPECIFICATION FORMAT (for every accepted bot)

```yaml
bot_id: regime_green_ic_spy
version: 1.0.0
thesis_file: proposals/2026-04-21-regime-green-ic-spy.md

underlying:
  class: A  # SPY/QQQ/IWM
  symbol: SPY

regime_gates:  # evaluated in order, all must pass
  - type: vix_level_max
    value: 22
  - type: vix_vix3m_max
    value: 1.00
  - type: vix_10d_high_max
    value: 30
  - type: vix_1d_change_max
    value: 0.15
  - type: ivp_min
    value: 30
  - type: gex_positive_required
    value: true
  - type: regime_score_max
    value: 3  # GREEN-YELLOW only
  - type: earnings_blackout
    value: true  # no effect on SPY; required on singles
  - type: fomc_cpi_nfp_blackout
    value: true

structure:
  type: iron_condor
  short_call_delta: 0.18
  long_call_delta: 0.06
  short_put_delta: 0.18
  long_put_delta: 0.06

entry:
  dte_min: 32
  dte_max: 45
  min_credit: 0.60
  min_reward_risk: 0.20
  max_bid_ask: 0.15
  max_spread_width: 7.50
  scan_time: "09:45"  # or "10:30" for timing-edge bots

exit:
  profit_target_pct: 50
  stop_loss_credit_multiple: 2.0
  time_exit_dte: 21
  regime_flip_exit: true  # close if regime flips to RED mid-trade

sizing:
  contracts_per_trade: 1  # paper phase
  max_concurrent: 3
  allocation_usd: 5000

validation:
  deflated_sharpe_ratio: 1.42
  pbo: 0.18
  cpcv_folds_won: 5
  oos_trade_count: 87
  max_drawdown_pct: 8.3
  correlation_vs_aryan_optimized: 0.34
  correlation_vs_iron_butterfly: 0.12

oa_buildable: true
estimated_build_time_minutes: 35
```

---

## WHAT YOU WILL NOT DO

- Do not attempt to automate Option Alpha (no API, don't try Computer Use, don't try Playwright)
- Do not execute live trades or connect to any broker
- Do not invent novel strategy structures outside the OA-buildable list
- Do not tune the gates during Phase 3 (they're frozen after Checkpoint 2)
- Do not accept a config with DSR < 1.0 regardless of raw Sharpe
- Do not skip thesis generation to save time
- Do not touch `tests/regression/golden/` without explicit instruction
- Do not modify `CLAUDE.md` mid-session (breaks prompt cache)
- Do not run Phase N+1 until `.phase_N_status.json` shows pass
- Do not silently fill missing data with interpolation — error loudly instead
- Do not use float for money aggregation
- Do not trust any Greek you didn't test against a hand-computed value

---

## FIRST ACTIONS (do these immediately in this order)

1. Read `PROJECT_BRIEF.md` and `CLAUDE.md` if they exist.
2. Inventory the repo. Check what scaffolding is present. Report to me.
3. Install Polygon MCP server (`polygon-io/mcp_polygon`) and GitHub MCP if not already configured.
4. Verify Polygon plan limits by calling the rate-limit documentation endpoint. Report actual limits.
5. Enter Plan Mode (Shift+Tab) and produce a detailed implementation plan for Phase 0 only. Do not write code yet. Show me the plan.
6. Wait for my approval before executing Phase 0.

Then proceed: Phase 0 → Checkpoint 0 (data ready) → Phase 1 → **Checkpoint 1 (pause)** → Phase 2 → **Checkpoint 2 (pause)** → Phase 3a → **Checkpoint 3 (pause)** → Phase 3b+3c → Phase 4 → Phase 5 → **Checkpoint 4 (pause, deliverables review)**.

---

## THE ONE RULE THAT OVERRIDES EVERYTHING

If at any point you are uncertain whether a specific output, configuration, or decision violates one of the 12 Hard Constraints, stop and ask me. Do not guess, do not infer intent, do not "make a reasonable assumption." The cost of pausing is hours. The cost of proceeding with a subtle constraint violation is a blown bot months later. Pause always wins.

Begin.
