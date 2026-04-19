# CLAUDE.md — `delta-optimizer` session rules

You are working in `delta-optimizer`, a research repo whose canonical specification is `PROJECT_BRIEF.md`. Everything in this file is harness rules. Everything in `PROJECT_BRIEF.md` is the project itself.

## Read at session start (in order)

1. `PROJECT_BRIEF.md` — full canonical spec. Re-read every session.
2. The most recent `data/results/.phase_N_status.json` to learn current phase state.
3. The most recent `checkpoints/checkpoint_*.md` for human-readable context.
4. The latest `git log -5` for recent activity.

## Session rules

- **Plan mode required** at every phase transition (Phase 0 → 1, 1 → 2, etc.) and before any change to backtest semantics, regime score construction, validation thresholds, or strategy structure. Direct edits OK only for one-line fixes, docstrings, renames, and single failing tests.
- **Commit after every green test.** Conventional message format. Phase boundaries get tags (`phase-0-scaffold`, `phase-1-complete`, etc.).
- **Never edit this file (`CLAUDE.md`) mid-session** — it breaks prompt cache. If a rule needs to change, ask the user first; they update it between sessions.
- **Never modify `tests/regression/golden/`** without an explicit, in-message instruction from Aryan to update goldens. Do not infer this intent from context.
- **Never run `Phase N+1` until** `data/results/.phase_N_status.json` exists and reports pass.
- **Never auto-tune past the explicit grids** in `PROJECT_BRIEF.md`. The 10-proposal cap (C12) and parameter discipline (G4-equivalent) are non-negotiable.
- **Stop and ask** if any decision could violate one of the 12 Hard Constraints (C1-C12). Pausing always wins.

## Coding conventions

- Python 3.11. `uv` for env + lock. `ruff` for lint + format. `mypy` strict on `src/delta_optimizer/`.
- Money is `Decimal`. Float allowed only inside vectorized BSM kernels. Aggregations are Decimal.
- Tests live in `tests/{unit,property,regression}/`. Every Greek and every aggregator has a known-answer unit test (no `approx(self_output)`).
- Property tests use Hypothesis. Required: put-call parity holds for every pricer.
- Look-ahead bias test: synthetic data such that any look-ahead produces a distinguishable PnL diff. Run every CI cycle.

## Data and ingest

- All Polygon API calls go through `src/delta_optimizer/ingest/polygon_client.py`. Direct `httpx.get(...)` to Polygon endpoints from anywhere else is forbidden — it bypasses cache and rate limiter.
- The canonical env var is `MASSIVE_API_KEY`; `POLYGON_API_KEY` is accepted as an alias for backwards compatibility (Polygon.io rebranded to Massive.com in 2025).
- Cache hits are silent; cache misses log at INFO; rate-limit hits log at WARN; 429s log at ERROR and surface `Retry-After`.
- Never silently interpolate missing data. Error loudly with the (underlying, date, endpoint) tuple.

## OA buildability check

- Anything emitted as a "bot" must pass `src/delta_optimizer/validate/oa_compat.py::validate_against_oa_dsl()` before being written to `data/results/phase_3/accepted/`.
- Forbidden structures: calendars, diagonals, strangles, straddles, ratio spreads, multi-expiry. Allowed: long/short stock, long/short option, vertical credit/debit spreads, iron condor, iron butterfly. (See `PROJECT_BRIEF.md` C1.)

## Subagents

- Use the `Explore` subagent for "find every place we compute X" queries.
- Use a dedicated `backtest-validator` subagent (defined at `.claude/agents/backtest-validator.md`) to run the regression suite after any edit under `pricing/` or `backtest/`. Returns pass/fail + diff summary, not full output.
- Use the `Plan` subagent for any plan-mode design that touches more than one module.

## Context management

- When context approaches 60%, manually run `/compact Keep current phase, file being edited, last test result. Drop earlier phase detail.` Do not wait for auto-compact at the limit; context rot starts well before.
- At session-end, before disconnecting, write the session's outputs to a checkpoint markdown so the next session can pick up cold.

## What this repo does NOT do

- No live trading, no order routing, no broker connection.
- No automation of Option Alpha (no Computer Use, no Playwright). All bots are manually built by Aryan from the emitted specs.
- No deep learning. Sample size doesn't support it.
- No stock-selection / alpha models. Strictly credit-spread parameter optimization.

## Quick reference paths

- Canonical spec: `PROJECT_BRIEF.md`
- Reusable validation math (DSR/PBO/CPCV) was copied from `C:/Users/aaash/optuna-screener/apex/validation/` in Phase 0; see `src/delta_optimizer/validate/`.
- Sample existing-bot configs (Aryan Optimized, Iron Butterfly, etc.) live under `C:/Users/aaash/Documents/AryanClawWorkspace/Options-claw/`. Read-only reference for differentiation checks (C7).
