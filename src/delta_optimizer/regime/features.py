"""Regime feature computation for Phase 1.

Pulls cached data via the manifest, builds a per-trading-day DataFrame of:
  vix_close, vix_10d_high, vix_1d_change, vix3m_close, vix_vix3m_ratio,
  vvix_close, skew_close, vix_iv_percentile_252d (proxy for SPY ATM 30d IV),
  spy_close, realized_vol_20d (annualized), forward_5d_rv (look-ahead, only
  used for VALIDATION not for live regime decisions).

GEX is intentionally NOT computed here — Phase 1 runs a 3-factor regime
classifier; the 4th factor is deferred until Phase 2 chain backfill lands.
"""

from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from delta_optimizer.ingest.cache import DiskCache

log = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


# --- raw data loaders (read from DiskCache by source/symbol) ---


@dataclass
class CachedDataLoader:
    cache_dir: Path

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache = DiskCache(self.cache_dir)

    def _load_payload(self, key: str) -> dict | None:
        return self.cache.get(key)

    def _find_endpoint(self, predicate) -> str | None:
        """Return the first cache key whose endpoint matches `predicate`."""
        for row in self.cache.manifest_rows():
            if predicate(row["endpoint"]):
                return row["key"]
        return None

    def yahoo_index(self, name: str) -> pd.DataFrame:
        """Load a Yahoo index series (VIX, VIX3M, VVIX, SKEW). Returns DataFrame
        indexed by date with columns: open, high, low, close, volume.
        """
        from delta_optimizer.ingest.yfinance_client import YAHOO_INDEX_SYMBOLS

        sym = YAHOO_INDEX_SYMBOLS[name]
        endpoint = f"yahoo/{sym}"
        key = self._find_endpoint(lambda e: e == endpoint)
        if key is None:
            raise FileNotFoundError(f"No cached Yahoo data for {name} (endpoint={endpoint})")
        payload = self._load_payload(key)
        if payload is None:
            raise FileNotFoundError(f"Cache miss for key={key}")
        rows = payload["rows"]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date").sort_index()

    def polygon_ohlc(self, ticker: str) -> pd.DataFrame:
        """Load Polygon EOD OHLC for a ticker. Returns DataFrame indexed by date
        with columns: open, high, low, close, volume.
        """
        endpoint_prefix = f"v2/aggs/ticker/{ticker}/range/1/day/"
        # Pick the cached entry with the widest date range.
        best_key, best_span = None, -1
        for row in self.cache.manifest_rows():
            ep = row["endpoint"]
            if not ep.startswith(endpoint_prefix):
                continue
            # Endpoint format: ".../range/1/day/{start}/{end}"
            parts = ep.rsplit("/", 2)
            if len(parts) < 3:
                continue
            try:
                start = datetime.strptime(parts[-2], "%Y-%m-%d").date()
                end = datetime.strptime(parts[-1], "%Y-%m-%d").date()
            except ValueError:
                continue
            span = (end - start).days
            if span > best_span:
                best_span = span
                best_key = row["key"]
        if best_key is None:
            raise FileNotFoundError(f"No cached Polygon OHLC for {ticker}")
        payload = self._load_payload(best_key)
        if payload is None:
            raise FileNotFoundError(f"Cache miss for key={best_key}")
        results = payload.get("results", [])
        if not results:
            raise ValueError(f"Cached Polygon response for {ticker} has no results")
        df = pd.DataFrame(results).rename(
            columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "ts"}
        )
        df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.normalize()
        return df.set_index("date")[["open", "high", "low", "close", "volume"]].sort_index()


# --- pure feature functions (no I/O, all unit-testable with synthetic data) ---


def realized_vol_annualized(closes: pd.Series, window: int = 20) -> pd.Series:
    """Annualized close-to-close realized vol over a rolling window.

    Formula: sqrt(252) * stddev(log returns) over `window` bars.
    Uses sample stddev (ddof=1).
    """
    log_ret = np.log(closes / closes.shift(1))
    return log_ret.rolling(window).std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)


def rolling_n_day_high(series: pd.Series, n: int = 10) -> pd.Series:
    """Trailing N-day high (inclusive of current bar)."""
    return series.rolling(n).max()


def daily_pct_change(series: pd.Series) -> pd.Series:
    """One-bar percent change as a decimal (0.05 = +5%)."""
    return series.pct_change()


def percentile_rank_rolling(series: pd.Series, window: int = 252) -> pd.Series:
    """Rolling percentile rank (0..100): fraction of last `window` values <= current.

    Formula matches the master prompt's "IV Percentile (252-day window on ATM
    30-DTE IV)". Returns NaN until the window is full.
    """
    def _pct(window_vals: np.ndarray) -> float:
        cur = window_vals[-1]
        return float(np.mean(window_vals <= cur) * 100.0)

    return series.rolling(window).apply(_pct, raw=True)


def vix_vix3m_ratio(vix: pd.Series, vix3m: pd.Series) -> pd.Series:
    """Contango/backwardation: VIX/VIX3M. >1.00 = backwardation (stress)."""
    return vix / vix3m


def forward_realized_vol(closes: pd.Series, horizon_days: int = 5) -> pd.Series:
    """Forward annualized realized vol over the next `horizon_days` trading days.

    USED ONLY FOR VALIDATION (Phase 1 ANOVA). Never feeds live regime decisions —
    this is a future-leak by definition.
    """
    log_ret = np.log(closes / closes.shift(1))
    # Reverse rolling: stddev of returns from t+1 to t+horizon.
    fwd = log_ret.shift(-horizon_days).rolling(horizon_days).std(ddof=1)
    # Re-align: at row t we want stddev of [t+1, ..., t+horizon]. The shift
    # above moved the t+horizon slice back by horizon, so a second shift aligns it.
    return (fwd.shift(-1) * np.sqrt(TRADING_DAYS_PER_YEAR))


def forward_max_drawdown(closes: pd.Series, horizon_days: int = 5) -> pd.Series:
    """Forward max intraday drawdown of close-to-close path over horizon."""
    out = pd.Series(index=closes.index, dtype=float)
    arr = closes.values
    for i in range(len(closes)):
        end = i + 1 + horizon_days
        if end > len(closes):
            out.iloc[i] = np.nan
            continue
        window = arr[i + 1 : end]
        if len(window) == 0:
            out.iloc[i] = np.nan
            continue
        peak = closes.iloc[i]
        running_min = window.min()
        out.iloc[i] = (running_min / peak) - 1.0  # negative for drawdown
    return out


# --- top-level feature builder ---


def build_feature_frame(loader: CachedDataLoader) -> pd.DataFrame:
    """Assemble the per-day feature DataFrame from cached data.

    Returns DataFrame indexed by trading date (intersection of VIX+VIX3M+SPY)
    with columns:
      vix_close, vix_10d_high, vix_1d_change, vix3m_close, vix_vix3m,
      vvix_close, skew_close, vix_ivp_252d, spy_close, rv_20d,
      fwd_rv_5d, fwd_max_dd_5d
    """
    vix = loader.yahoo_index("VIX")["close"].rename("vix_close")
    vix3m = loader.yahoo_index("VIX3M")["close"].rename("vix3m_close")
    vvix = loader.yahoo_index("VVIX")["close"].rename("vvix_close")
    skew = loader.yahoo_index("SKEW")["close"].rename("skew_close")
    spy = loader.polygon_ohlc("SPY")["close"].rename("spy_close")

    df = pd.concat([vix, vix3m, vvix, skew, spy], axis=1).dropna(subset=["vix_close", "spy_close"])

    df["vix_10d_high"] = rolling_n_day_high(df["vix_close"], 10)
    df["vix_1d_change"] = daily_pct_change(df["vix_close"])
    df["vix_vix3m"] = vix_vix3m_ratio(df["vix_close"], df["vix3m_close"])
    df["vix_ivp_252d"] = percentile_rank_rolling(df["vix_close"], 252)
    df["rv_20d"] = realized_vol_annualized(df["spy_close"], 20)
    df["fwd_rv_5d"] = forward_realized_vol(df["spy_close"], 5)
    df["fwd_max_dd_5d"] = forward_max_drawdown(df["spy_close"], 5)

    return df


def write_feature_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=True)
