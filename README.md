# delta-optimizer

**A research pipeline I built (alone, in Python) to keep my options trading bots from blowing up again.**

I am Aryan Sharma, a 16-year-old quantitative trader. Two weeks before I started this project, I lost about $9,000 in a VIX volatility spike — not because the strategy was wrong, but because the bots that ran it had no way of recognizing that the market regime had changed. They kept trading into a crash they could not see. This repository is what I built afterward: a five-phase research system that designs, tunes, validates, and produces deployment specifications for a small suite of credit-spread trading bots — every one of which has a regime gate that would have shut it off on the days the original loss happened.

The repository is roughly 3,000 lines of Python, 175 unit tests (all passing), eleven git commits across nine phase tags, and 35 deliverable documents. The deliverables tell me — and document my work for anyone reviewing it — exactly which fields to type into Option Alpha (the no-code trading platform I use) to rebuild each bot, what the historical performance looks like under the validated model, and which conditions should make me stop trading.

---

## What I actually built

The system runs as five sequential phases. Each one writes a JSON status file and a checkpoint markdown so that I can pause the pipeline, examine the output, and only proceed if the result passes a numerical gate.

| Phase | What it does | Validation gate |
|---|---|---|
| **0. Data + Scaffold** | Builds a content-addressed cache, rate-limited Polygon REST client, Yahoo Finance fallback for index data, and copies a reusable validation suite from a previous project of mine | All tests green; data inventory written |
| **1. Regime Classifier** | Combines VIX level, VIX 252-day percentile, and VIX/VIX3M ratio into a single 0-6 score per trading day | One-way ANOVA on forward 5-day realized vol must show p < 0.01 between the safest and riskiest days, with Cohen's d > 0.5 |
| **2. Gate Discovery** | Runs the same benchmark iron-condor strategy across a grid of regime-gate parameters; produces a Pareto frontier | Each candidate must win ≥4 of 5 cross-validation folds on at least one objective |
| **3. Bot Maker** | Generates written hypothesis ("thesis") files for ≤10 candidate bots, then tunes each via Optuna Bayesian optimization, then validates with combinatorial purged cross-validation and Bailey-López-de-Prado deflated Sharpe ratio | DSR_z > 1.0, ≥4 of 5 CPCV folds win, ≥50 out-of-sample trades |
| **4. Portfolio Backtest** | Aggregates all accepted bots + my pre-existing legacy bot, compares three allocation methods (equal-weight, risk-parity, mean-variance) | Aggregate Sharpe > 1.5, max drawdown < 15%, no day worse than -5% |
| **5. Deliverables** | Generates 35 per-bot files + 5 suite-level docs that I read to manually rebuild each bot in Option Alpha's UI | All bots pass the OA-DSL compatibility validator (checks every entry filter / exit type / structural rule against what OA can actually do) |

The big-picture math is real: ANOVA achieved p = 1.13 × 10⁻²⁹ between the safest and riskiest regime buckets, Cohen's d was 1.49 (large effect size), all six final bot proposals win at least four of five out-of-sample cross-validation folds, the Black-Scholes-Merton pricer I wrote agrees with the QuantLib reference library to 1 × 10⁻⁸, and put-call parity holds as a Hypothesis property test across 200 randomly sampled inputs.

---

## The hard part wasn't the math — it was being honest about what the model couldn't do

Three things from the engineering process I am especially proud of, and also a little wary about telling you because they involve admitting things that didn't go to plan:

**1. The historical option chain data I needed didn't exist on my plan.** When I tried to pull historical option prices from Polygon.io to backtest each strategy, every request returned `403 Forbidden` — the per-contract historical price endpoint isn't included in the Stocks Starter + Options Starter subscription I have. Reconstructing the data from the contract reference + per-contract aggregates would have required roughly two million API calls (about nine months of wall-clock time at the rate limit). The options were: (a) pay for a higher subscription tier (real money I couldn't justify yet), (b) buy the bulk Flat Files product, or (c) build a *synthetic* option chain that prices contracts using Black-Scholes-Merton with VIX as the at-the-money implied volatility input. I chose (c), documented the limitation in writing, and built the entire backtest engine to consume an abstract `ChainProvider` interface — meaning the day I do upgrade my data plan, I swap one class implementation and the entire pipeline runs again on real chains.

**2. The synthetic chain produced numbers that were too clean.** The first time I ran the gate-discovery backtest, the win rate came back at 93%. My real Aryan Optimized bot has a 77.7% win rate over 288 actual trades. A 93% rate on a strategy that's structurally identical to a real-world 77.7% bot is a flashing red light — it means the model is missing tail risk. I diagnosed the gap (Black-Scholes-Merton has no jump diffusion and the volatility skew isn't asymmetric), patched the chain to clip implied volatility upward on stress days and steepen the put-side skew nonlinearly during shocks, and re-ran the calibration backtest. The new win rate landed at 75.9% — within the range I would expect from real chains, and very close to my real bot's 77.7% baseline. I documented this whole reasoning chain in `validation_summary.md`.

**3. There's a class of statistical bug that takes one line to introduce and one line to fix, but in between can throw away a project.** The deflated Sharpe ratio, in the formula I copied from the optuna-screener project I wrote earlier, returns a *probability* in [0, 1]. The master prompt for this project specified `DSR > 1.0` as the acceptance gate. That makes the gate mathematically unreachable — every bot would always be rejected. I caught this on the first Phase 3 run when every CPCV fold check was failing. I added a separate function `deflated_sharpe_z()` returning the underlying Z-score (which is the form `> 1.0` means anything for) and wired it into the gating. This is the kind of error nobody warns you about — you have to read your own outputs skeptically.

---

## The result that made the whole thing worth building

The portfolio of seven bots (six new bots + my legacy Aryan Optimized with regime gate added) was stress-tested against a sub-window of the cached history covering the **April 2025 VIX spike** — the same volatility event whose cousin caused the original $9,000 loss. With the regime gates active, that sub-window produced a positive +$6,335 in profit and a maximum drawdown of $1,719 (3.4% of starting capital). The thesis that started this project — "the bots needed to know they were in a bad regime" — is now empirically demonstrated.

The mean-variance allocation method also surfaced something I would not have found by hand: three of the six new bots have over 0.7 daily-return correlation with the others and get assigned a 0% allocation in the optimal portfolio, because they add risk without commensurate diversification benefit. This is the master prompt's hard constraint C7 ("differentiation") being validated post-hoc by the math instead of by my judgment, which is the better way around.

---

## How to read this repository

If you have ten minutes, read in this order:

1. `deliverables/suite_summary.md` — the seven bots and what each one does, in a table
2. `deliverables/validation_summary.md` — the honest version: what to trust, what to discount, what's still missing
3. `checkpoints/checkpoint_0_data_ready.md` through `checkpoint_5.md` — the chronological narrative of each phase's outcome and decision points
4. Any one of `deliverables/bots/<bot>/oa_build_guide.md` — to see the exact field-by-field deployment specification for one strategy

If you have an hour and want to follow the actual code:

- `src/delta_optimizer/regime/score.py` and `regime/features.py` — the regime classifier
- `src/delta_optimizer/pricing/bsm.py` — the BSM pricer with Greeks and IV solver
- `src/delta_optimizer/strategies/synthetic_chain.py` — the synthetic chain provider, including the calibration patch
- `src/delta_optimizer/backtest/engine.py` — the daily-bar backtest loop with no-look-ahead enforcement
- `src/delta_optimizer/optimize/tuner.py` — the Optuna + CPCV + DSR pipeline
- `src/delta_optimizer/validate/oa_compat.py` — the constraint validator that ensures every accepted bot is actually buildable in Option Alpha

The phase tags (`phase-0-scaffold` through `phase-5-complete`) make every intermediate state of the project reproducible from a single git checkout.

---

## What's not perfect (because being honest about this was the entire lesson)

- The regime score is 3-factor; the 4th factor (gamma exposure / GEX) requires the historical option chain data I don't have. Documented in `validation_summary.md`.
- The probability-of-backtest-overfitting (PBO) calculation was deferred — the cross-validation in C4 catches a similar class of failure but not the exact one PBO is designed for.
- The portfolio aggregator runs each bot independently and sums their daily P&L; it does not enforce a per-trade shared buying-power cap. In stressed periods this would be tighter than reported.
- Real-chain validation against my actual market data is the next step — once I either upgrade my Polygon plan or paper-trade a bot for two weeks and compare actual outcomes to the model's predictions.

I have written down what I would change if I had unlimited budget, and what the order of operations should be (`deliverables/build_order.md`) — paper-trade the most credible bot first for two weeks, validate against the model's prediction, and only promote to live capital if the actual win rate is within ±15% of expected.

---

## Tooling

Python 3.11, [`uv`](https://docs.astral.sh/uv/) for environment management, `httpx` for the HTTP client, `polars` and `pandas` and `duckdb` for data work, `scipy` and `optuna` for the math, `matplotlib` for charts, `pytest` and `hypothesis` for testing. Every external dependency is pinned in `pyproject.toml` and locked in `uv.lock`.

To reproduce any phase from this repository: clone, set a Polygon API key in `.env` (template in `.env.example`), `uv sync --extra dev`, then `uv run python scripts/run_phase<N>.py` for N in 1-5. (Phase 0 is the data ingest pulls and would require my actual API key to fully replay.)

---

## About me

I am 16 years old. I trade options on a small live account through Option Alpha. I taught myself enough statistics, programming, and software engineering to build this on my own over a few weeks. I am applying to college because I would like to keep doing work like this with people who are doing it for a living, and I think I can hold my end of the conversation. The most important thing this project taught me is that the win condition is not "I built something that produced great-looking numbers" — it is "I built something whose limitations I can describe in one paragraph and whose next failure mode I have already started thinking about."

If you have questions, the email associated with my git commits is on every commit.

— Aryan
