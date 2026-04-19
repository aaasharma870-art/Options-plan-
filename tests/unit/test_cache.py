"""DiskCache — round-trip, hash determinism, manifest correctness."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from delta_optimizer.ingest.cache import DiskCache, _stable_params_json, cache_key


class TestCacheKey:

    def test_same_params_same_hash(self) -> None:
        a = cache_key("v2/aggs", {"ticker": "SPY", "limit": 100})
        b = cache_key("v2/aggs", {"limit": 100, "ticker": "SPY"})
        assert a == b  # order-independent

    def test_different_params_different_hash(self) -> None:
        a = cache_key("v2/aggs", {"ticker": "SPY"})
        b = cache_key("v2/aggs", {"ticker": "QQQ"})
        assert a != b

    def test_different_endpoint_different_hash(self) -> None:
        a = cache_key("v2/aggs/A", {"x": 1})
        b = cache_key("v2/aggs/B", {"x": 1})
        assert a != b

    def test_none_params_equals_empty(self) -> None:
        assert cache_key("e", None) == cache_key("e", {})

    def test_stable_params_json_sorts_keys(self) -> None:
        out = _stable_params_json({"b": 2, "a": 1, "c": 3})
        assert out == '{"a":1,"b":2,"c":3}'

    def test_known_answer_sha_64_hex(self) -> None:
        # Hash should always be 64 hex chars (SHA256).
        h = cache_key("foo", {"x": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestDiskCacheRoundTrip:

    def test_put_then_get(self, tmp_path: Path) -> None:
        c = DiskCache(tmp_path)
        key = cache_key("e", {"a": 1})
        assert c.get(key) is None
        n = c.put(key, {"hello": "world"}, "e", {"a": 1}, "2026-04-19T00:00:00Z")
        assert n > 0
        assert c.get(key) == {"hello": "world"}

    def test_idempotent_put(self, tmp_path: Path) -> None:
        c = DiskCache(tmp_path)
        key = cache_key("e", {"a": 1})
        c.put(key, {"v": 1}, "e", {"a": 1}, "ts1")
        n = c.put(key, {"v": 999}, "e", {"a": 1}, "ts2")  # ignored
        assert n == 0
        # Original value preserved.
        assert c.get(key) == {"v": 1}

    def test_storage_layout(self, tmp_path: Path) -> None:
        c = DiskCache(tmp_path)
        key = cache_key("e", {"a": 1})
        c.put(key, {"v": 1}, "e", {"a": 1}, "ts")
        expected = tmp_path / key[:2] / f"{key}.json.gz"
        assert expected.exists()
        # File is gzip JSON.
        with gzip.open(expected, "rb") as f:
            assert json.loads(f.read().decode("utf-8")) == {"v": 1}

    def test_manifest_appends(self, tmp_path: Path) -> None:
        c = DiskCache(tmp_path)
        c.put(cache_key("e1", {}), {"x": 1}, "e1", {}, "ts1")
        c.put(cache_key("e2", {}), {"x": 2}, "e2", {}, "ts2")
        rows = c.manifest_rows()
        assert len(rows) == 2
        assert {r["endpoint"] for r in rows} == {"e1", "e2"}
        assert all("bytes" in r and r["bytes"] > 0 for r in rows)

    def test_manifest_missing_returns_empty(self, tmp_path: Path) -> None:
        c = DiskCache(tmp_path)
        assert c.manifest_rows() == []
