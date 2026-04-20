# Checkpoint 0 — data infrastructure status

**Date:** 2026-04-19
**Phase 0 work completed:** repo scaffold, ingest layer, validation suite copied, 58 unit tests green, Massive MCP registered. **Quick data pulls done.** **Chain pull paused — needs your call before continuing.**

---

## What was pulled tonight

| Source | Dataset | Coverage | Cache size |
|---|---|---|---|
| Yahoo Finance | VIX, VIX3M, VVIX, SKEW (daily close) | 2022-01-03 → 2026-04-17, 1076 trading days each | ~74 KB |
| Polygon Stocks Starter | EOD OHLC: SPY, QQQ, IWM, AAPL, MSFT, NVDA, META, GOOGL, AMZN, TSLA | 2022-01-03 → 2026-04-17 | ~350 KB |
| Polygon reference | `v3/reference/tickers/{TKR}` for AAPL, MSFT, NVDA, META, GOOGL, AMZN, TSLA | as-of pull | ~10 KB |
| Polygon options | **none yet — see below** | — | — |
| FRED DTB3 | **deferred** — needs your free FRED API key | — | — |

**Total cache:** 22 entries / ~435 KB. Manifest at `data/raw/manifest.jsonl`.

**Rate limiter behavior:** bucket bootstrapped at 4 req/min (5 - 20% safety per `PROJECT_BRIEF.md`); Polygon did not return `X-RateLimit-Limit` headers, so the probe held the conservative value. Real Polygon calls saw ~15s waits between requests, confirming the limiter works. No 429s.

---

## Findings that matter

### 1. Indices need Yahoo (your decision, executed)
Polygon Stocks Starter + Options Starter does not include indices. `I:VIX` returns **403 Forbidden**. Per your call we route VIX/VIX3M/VVIX/SKEW through Yahoo via `yfinance`. Same `DiskCache`, same JSON-safe shape — downstream code sees no difference.

### 2. FRED key not set
DTB3 (risk-free rate) pull was scaffolded but skipped — `FRED_API_KEY` is empty in your `.env`. Free key from `fredaccount.stlouisfed.org/apikey` — paste into `.env` and re-run `uv run python scripts/pull_fred.py` whenever you want. **Not blocking** Phase 1 regime work; needed for Greeks pricing in Phase 2.

### 3. Earnings dates are deferred to Phase 1
The reference endpoint I pulled gets ticker metadata, not the earnings calendar. The full earnings calendar lives behind `v3/reference/dividends` (proxy) or `vX/reference/earnings` (paid feature on some plans). I'll structure this properly in Phase 1 when the regime classifier needs it.

### 4. **Option chain backfill is a much bigger problem than the master prompt scoped.** ⚠️

The master prompt asks for "EOD chain snapshots, 0-60 DTE | Same 10 tickers | 2022-01-01 to yesterday." Looking at this more carefully tonight:

- Polygon's `/v3/snapshot/options/{underlying}` endpoint returns the **live** chain only — it has no "as_of date" parameter for historical snapshots.
- True historical chain reconstruction means: (a) for each (date, underlying), call `/v3/reference/options/contracts?underlying_ticker=SPY&as_of=DATE` to get the contract list active that day, (b) for each contract on that day, call `/v2/aggs/ticker/O:SPY...` to get its EOD price.
- For 10 underlyings × ~1000 trading days × ~200 active contracts/day in 0-60 DTE band ≈ **2,000,000 API calls minimum**.
- At 5 req/min (Options Starter's published limit) that's ≈ 9 months of wall-clock pulling. Even at 100 req/min it's 14 days.

This isn't a "kick off overnight" job. It's a multi-week design problem.

**Three honest paths forward — your call:**

| Option | What it is | Trade-offs |
|---|---|---|
| **A. Polygon Flat Files (S3 bulk)** | Polygon sells daily options OHLCV files via S3 (`flatfiles.polygon.io`). One file = one trading day = all option contracts. Stocks Starter + Options Starter typically includes flat-file access; verify with your account dashboard. Pull historical = ~1000 file downloads = a few hours. | Cheapest by far if your plan includes it. Best path. |
| **B. Scoped backfill** | Backfill only what's needed: (i) ATM ±15 strikes, (ii) 0-60 DTE only, (iii) start with 6 months of history not 4 years. ~30-50k API calls; ~1-3 days at 5/min. | Compromises Phase 1's regime separation if 4 years is needed for ANOVA. |
| **C. Forward pull + sparse historical** | Daily cron from now forward; opportunistically backfill ATM strikes during low-rate hours. | Phase 1 may not have enough history when we want to start. |
| **D. Upgrade Polygon plan** | Bump to Polygon Options Advanced or Developer; published limit is 100/min. Cuts wall-clock to days. | Cost. |

I have not started any chain backfill. I'm not picking the option for you because the cost / Phase-1-readiness trade-off is yours.

---

## Verification (Phase 0 acceptance, per the plan)

| Item | State |
|---|---|
| `uv run pytest tests/unit -q` | ✅ 58 passed |
| `uv run python scripts/pull_polygon.py --dry-run` | ✅ prints plan, probed bucket |
| `claude mcp list` | ✅ `massive: ✓ Connected` (GitHub MCP intentionally skipped) |
| `data/raw/manifest.jsonl` lists pulled rows | ✅ 22 rows |
| Git tag `phase-0-scaffold` | ✅ committed |

The original plan also expected the chain backfill to be running. That's what's paused. Renaming this checkpoint accurately as **"data infrastructure ready, chain backfill blocked on design decision."**

---

## What I need from you to unblock Phase 1

1. **Pick a chain-backfill path** (A / B / C / D above). I can start tonight on whichever you choose.
2. **Optional:** drop your FRED API key into `.env` if you have one. Not blocking Phase 1, but it'll be needed for Phase 2 Greeks.

Phase 1 (regime classifier) needs:
- VIX-family time series ✅ have it
- Realized vol from SPY OHLC ✅ have it
- IV percentile from option chains ❌ chains needed
- GEX proxy from SPY chain OI × gamma ❌ chains needed

So roughly half of Phase 1 can start with what's cached. The other half waits on the chain decision.

---

## Open log

- The Polygon `X-RateLimit-Limit` header was absent on every response we saw. The bucket stays conservative at 4/min until either the header appears or you tell me your plan's actual limit. Want me to assume 5/min flat?
- `optuna-screener/.env` had a `POLYGON_API_KEY=...` value. Same key was copied into `delta-optimizer/.env`. Both `MASSIVE_API_KEY` and `POLYGON_API_KEY` env var names resolve in code; neither file is in git (both `.env` files are gitignored).
