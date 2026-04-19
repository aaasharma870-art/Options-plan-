"""PolygonClient against httpx.MockTransport.

Verifies: cache hit/miss path, rate-limit probe from headers,
429 backoff (bucket halves), and api_key resolution.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from delta_optimizer.ingest.polygon_client import (
    PolygonClient,
    PolygonError,
    RateLimitExhausted,
    _resolve_api_key,
)


def _ok(payload: dict, *, rate_limit_header: str | None = "100") -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if rate_limit_header is not None:
        headers["X-RateLimit-Limit"] = rate_limit_header
    return httpx.Response(200, headers=headers, content=json.dumps(payload).encode())


class TestApiKeyResolution:

    def test_explicit_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MASSIVE_API_KEY", "from-env")
        assert _resolve_api_key("explicit") == "explicit"

    def test_massive_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POLYGON_API_KEY", raising=False)
        monkeypatch.setenv("MASSIVE_API_KEY", "m")
        assert _resolve_api_key(None) == "m"

    def test_polygon_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
        monkeypatch.setenv("POLYGON_API_KEY", "p")
        assert _resolve_api_key(None) == "p"

    def test_no_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
        monkeypatch.delenv("POLYGON_API_KEY", raising=False)
        with pytest.raises(PolygonError):
            _resolve_api_key(None)


class TestPolygonClient:

    def _make_client(
        self,
        tmp_path: Path,
        handler,
        *,
        bootstrap: int = 4,
    ) -> PolygonClient:
        transport = httpx.MockTransport(handler)
        http = httpx.Client(transport=transport)
        return PolygonClient(
            api_key="test",
            cache_dir=tmp_path,
            bootstrap_per_min=bootstrap,
            client=http,
        )

    def test_cache_hit_avoids_network(self, tmp_path: Path) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return _ok({"results": [1, 2, 3]})

        c = self._make_client(tmp_path, handler)
        a = c.get("v2/aggs/ticker/SPY/range/1/day/2024-01-01/2024-01-02")
        b = c.get("v2/aggs/ticker/SPY/range/1/day/2024-01-01/2024-01-02")
        assert a == b == {"results": [1, 2, 3]}
        assert calls["n"] == 1  # second call hit cache

    def test_rate_limit_probe_resizes_bucket(self, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _ok({"ok": True}, rate_limit_header="100")

        c = self._make_client(tmp_path, handler, bootstrap=4)
        assert c.bucket.capacity == 4.0
        c.get("v2/test")
        # Probed: 100/min × 0.8 = 80
        assert c.bucket.capacity == pytest.approx(80.0)
        assert c.bucket.refill_per_sec == pytest.approx(80.0 / 60.0)

    def test_no_rate_limit_header_keeps_bootstrap(self, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _ok({"ok": True}, rate_limit_header=None)

        c = self._make_client(tmp_path, handler, bootstrap=4)
        c.get("v2/test")
        assert c.bucket.capacity == 4.0

    def test_429_halves_bucket_then_succeeds(self, tmp_path: Path) -> None:
        # No rate-limit header on the success response so the probe doesn't
        # immediately resize the (already-halved) bucket.
        responses = iter([
            httpx.Response(429, headers={"Retry-After": "0"}, content=b""),
            _ok({"ok": True}, rate_limit_header=None),
        ])

        def handler(request: httpx.Request) -> httpx.Response:
            return next(responses)

        c = self._make_client(tmp_path, handler, bootstrap=10)
        result = c.get("v2/test")
        assert result == {"ok": True}
        assert c.bucket.capacity == 5.0  # halved from 10, no probe

    def test_429_exhausted_raises(self, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"}, content=b"")

        c = self._make_client(tmp_path, handler, bootstrap=10)
        with pytest.raises(RateLimitExhausted):
            c.get("v2/test")

    def test_404_surfaces_error(self, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"")

        c = self._make_client(tmp_path, handler)
        with pytest.raises(PolygonError):
            c.get("v2/test")

    def test_apikey_excluded_from_cache_key(self, tmp_path: Path) -> None:
        """Two calls with different (rotated) api keys still hit the same cache row."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return _ok({"ok": True})

        c1 = self._make_client(tmp_path, handler)
        c1.api_key = "key-A"
        c1.get("v2/x")
        c1.api_key = "key-B"
        c1.get("v2/x")
        assert calls["n"] == 1
