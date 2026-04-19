"""Yahoo Finance fallback for VIX-family indices.

Polygon Stocks/Options Starter does not include indices. We fetch
^VIX, ^VIX3M, ^VVIX, ^SKEW from Yahoo via yfinance — free, no key,
but yfinance is unofficial and may break. Cached on disk via DiskCache.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delta_optimizer.ingest.cache import DiskCache, cache_key

log = logging.getLogger(__name__)

# Yahoo symbols for the four indices the regime classifier wants.
YAHOO_INDEX_SYMBOLS = {
    "VIX": "^VIX",
    "VIX3M": "^VIX3M",
    "VVIX": "^VVIX",
    "SKEW": "^SKEW",
}


class YFinanceError(RuntimeError):
    pass


class YFinanceClient:
    """Disk-cached daily-close puller for Yahoo indices.

    yfinance import is lazy so the package can be imported without it.
    """

    def __init__(self, cache_dir: Path | str = "data/raw") -> None:
        self.cache = DiskCache(Path(cache_dir))

    def daily_close(self, yahoo_symbol: str, start: str, end: str) -> dict[str, Any]:
        """Fetch daily OHLC + close for a Yahoo symbol. Returns JSON-safe dict."""
        key_params = {"symbol": yahoo_symbol, "start": start, "end": end}
        key = cache_key(f"yahoo/{yahoo_symbol}", key_params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        import yfinance as yf  # lazy

        df = yf.download(
            yahoo_symbol,
            start=start,
            end=end,
            progress=False,
            auto_adjust=False,
            interval="1d",
        )
        if df is None or df.empty:
            raise YFinanceError(f"yfinance returned empty for {yahoo_symbol} {start}..{end}")

        # Flatten possible MultiIndex columns (yfinance ≥ 0.2 returns ('Close', '^VIX')).
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        rows = []
        for ts, row in df.iterrows():
            rows.append(
                {
                    "date": ts.date().isoformat(),
                    "open": _safe_float(row.get("Open")),
                    "high": _safe_float(row.get("High")),
                    "low": _safe_float(row.get("Low")),
                    "close": _safe_float(row.get("Close")),
                    "volume": _safe_int(row.get("Volume")),
                }
            )

        payload = {
            "source": "yahoo",
            "symbol": yahoo_symbol,
            "rows": rows,
        }
        self.cache.put(
            key=key,
            value=payload,
            endpoint=f"yahoo/{yahoo_symbol}",
            params=key_params,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        return payload


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN check


def _safe_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
