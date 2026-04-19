"""FRED client (Federal Reserve Economic Data).

Used in Phase 0 for DTB3 (13-week T-bill rate, our risk-free rate proxy).
Cached on disk via the same DiskCache as Polygon for consistency.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delta_optimizer.ingest.cache import DiskCache, cache_key

log = logging.getLogger(__name__)


class FredError(RuntimeError):
    pass


class FredClient:
    """Thin wrapper around fredapi with disk cache.

    fredapi imports lazily so the package can be imported without it during
    Phase 0 dry-runs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | str = "data/raw",
    ) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self.api_key:
            raise FredError("FRED_API_KEY not set in env and no api_key passed")
        self.cache = DiskCache(Path(cache_dir))
        self._fred = None  # lazy

    def _get_fred(self):  # type: ignore[no-untyped-def]
        if self._fred is None:
            from fredapi import Fred  # type: ignore[import-not-found]

            self._fred = Fred(api_key=self.api_key)
        return self._fred

    def series(self, series_id: str, start: str, end: str) -> dict[str, Any]:
        """Fetch a FRED series. Returns {dates: [...], values: [...]} JSON-safe."""
        key_params = {"series": series_id, "start": start, "end": end}
        key = cache_key(f"fred/{series_id}", key_params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        fred = self._get_fred()
        s = fred.get_series(series_id, observation_start=start, observation_end=end)
        # Normalize to JSON-safe structure.
        payload = {
            "series": series_id,
            "dates": [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in s.index],
            "values": [None if v != v else float(v) for v in s.values],  # NaN check
        }
        self.cache.put(
            key=key,
            value=payload,
            endpoint=f"fred/{series_id}",
            params=key_params,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        return payload
