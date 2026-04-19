"""Polygon.io / Massive.com REST client.

Rate-limited (token bucket), cached (content-addressed disk), retry-aware.
Single entry point for all Polygon API calls in delta-optimizer.

The canonical env var is `MASSIVE_API_KEY`; `POLYGON_API_KEY` is accepted
as an alias (Polygon.io rebranded to Massive.com in 2025).
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from delta_optimizer.ingest.cache import DiskCache, cache_key
from delta_optimizer.ingest.rate_limiter import TokenBucket

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.polygon.io"
SAFETY_MARGIN = 0.8  # use 80% of the observed rate limit (per PROJECT_BRIEF.md)
BOOTSTRAP_PER_MIN = 4  # conservative: 5/min - 20% margin


class PolygonError(RuntimeError):
    pass


class RateLimitExhausted(PolygonError):
    """Raised on 429 after Retry-After waits or when caller chose to fail loudly."""


def _resolve_api_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    for name in ("MASSIVE_API_KEY", "POLYGON_API_KEY"):
        v = os.environ.get(name)
        if v:
            return v
    raise PolygonError(
        "No API key found. Set MASSIVE_API_KEY or POLYGON_API_KEY in env or pass api_key="
    )


class PolygonClient:
    """Single source of truth for Polygon REST calls.

    - All calls go through `get()` which checks cache, then rate-limits, then HTTP.
    - First successful response triggers `_probe_rate_limit()` to size the bucket.
    - Cache misses log INFO; rate-limit waits log WARN; 429s log ERROR.
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | str = "data/raw",
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = 5,
        timeout_s: float = 30.0,
        bootstrap_per_min: int = BOOTSTRAP_PER_MIN,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = _resolve_api_key(api_key)
        self.base_url = base_url.rstrip("/")
        self.cache = DiskCache(Path(cache_dir))
        self.bucket = TokenBucket(
            capacity=float(bootstrap_per_min),
            refill_per_sec=bootstrap_per_min / 60.0,
        )
        self.max_retries = max_retries
        self._probed = False
        self._client = client or httpx.Client(timeout=timeout_s)

    # --- low-level ---

    def _full_url(self, endpoint: str) -> str:
        if endpoint.startswith("http"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _probe_rate_limit(self, headers: httpx.Headers) -> None:
        """Read X-RateLimit-Limit and resize the bucket once on first success."""
        if self._probed:
            return
        raw = headers.get("X-RateLimit-Limit") or headers.get("x-ratelimit-limit")
        if not raw:
            log.info("rate_limit_probe: no X-RateLimit-Limit header; staying at bootstrap")
            self._probed = True
            return
        try:
            observed = float(raw)
        except ValueError:
            log.warning("rate_limit_probe: cannot parse header %r; staying at bootstrap", raw)
            self._probed = True
            return

        new_cap = max(1.0, observed * SAFETY_MARGIN)
        new_rate = new_cap / 60.0
        log.info(
            "rate_limit_probe: server reports %s/min, sizing bucket to %.1f/min (%.1f safety)",
            observed,
            new_cap,
            SAFETY_MARGIN,
        )
        self.bucket.update_capacity(new_cap, new_rate)
        self._probed = True

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        cache_ok: bool = True,
    ) -> dict[str, Any]:
        """Issue a GET. Cached, rate-limited, retried. Returns parsed JSON.

        `endpoint` may be a relative path or a fully-qualified URL (used for
        Polygon's `next_url` pagination).
        """
        params = dict(params or {})
        # Strip apiKey from cache key — it's an auth secret, not a query identity.
        key = cache_key(endpoint, {k: v for k, v in params.items() if k != "apiKey"})

        if cache_ok:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        params["apiKey"] = self.api_key
        url = self._full_url(endpoint)

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            wait_s = self.bucket.acquire(1.0)
            if wait_s > 0.5:
                log.warning("rate_limit_wait: waited %.2fs before %s", wait_s, endpoint)

            try:
                r = self._client.get(url, params=params)
            except httpx.HTTPError as e:
                last_err = e
                back = min(2 ** attempt, 30)
                log.warning("polygon_http_error attempt=%d err=%s; backoff=%ds", attempt, e, back)
                time.sleep(back)
                continue

            if r.status_code == 429:
                self.bucket.halve()
                retry_after = int(r.headers.get("Retry-After", "30"))
                log.error(
                    "polygon_429 attempt=%d retry_after=%ds endpoint=%s; bucket halved",
                    attempt,
                    retry_after,
                    endpoint,
                )
                if attempt == self.max_retries - 1:
                    raise RateLimitExhausted(
                        f"429 from {endpoint} after {self.max_retries} attempts"
                    )
                time.sleep(retry_after)
                continue

            if 500 <= r.status_code < 600:
                back = min(2 ** attempt, 30)
                log.warning("polygon_5xx %d attempt=%d backoff=%ds", r.status_code, attempt, back)
                time.sleep(back)
                continue

            if r.status_code == 404:
                # Cache 404 as None? No — surface it.
                raise PolygonError(f"404 from {endpoint} params={params}")

            r.raise_for_status()
            self._probe_rate_limit(r.headers)
            data = r.json()

            self.cache.put(
                key=key,
                value=data,
                endpoint=endpoint,
                params={k: v for k, v in params.items() if k != "apiKey"},
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
            return data

        raise PolygonError(f"polygon_exhausted endpoint={endpoint} last_err={last_err}")

    # --- typed convenience wrappers (only what Phase 0 pulls need) ---

    def aggs_daily(self, ticker: str, start: str, end: str) -> dict[str, Any]:
        """EOD OHLC aggs. ticker can be a stock (SPY) or index (I:VIX).

        start, end: ISO YYYY-MM-DD.
        """
        endpoint = f"v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
        return self.get(endpoint, params={"adjusted": "true", "sort": "asc", "limit": 50000})

    def option_chain_snapshot(
        self, underlying: str, expiration_lte: str | None = None
    ) -> dict[str, Any]:
        """Live (or as-of) chain snapshot. `expiration_lte` filters to <= a date.

        Note: snapshots are end-of-day for Stocks/Options Starter plans.
        """
        params: dict[str, Any] = {"limit": 250}
        if expiration_lte is not None:
            params["expiration_date.lte"] = expiration_lte
        return self.get(f"v3/snapshot/options/{underlying}", params=params)

    def ticker_reference(self, ticker: str) -> dict[str, Any]:
        """Reference metadata. Used to confirm ticker validity / get listing dates."""
        return self.get(f"v3/reference/tickers/{ticker}")

    def paginate(self, first_response: dict[str, Any]) -> list[dict[str, Any]]:
        """Walk `next_url` pagination, returning all pages (incl. the first)."""
        pages = [first_response]
        while True:
            nxt = pages[-1].get("next_url")
            if not nxt:
                break
            pages.append(self.get(nxt))
        return pages
