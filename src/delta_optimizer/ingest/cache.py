"""Content-addressed disk cache for Polygon responses.

Key: SHA256 of (endpoint, sorted_params_json).
Storage: gzip-compressed JSON at `<root>/<first2>/<sha>.json.gz`.
Manifest: append-only JSONL at `<root>/manifest.jsonl` for coverage queries.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _stable_params_json(params: dict[str, Any] | None) -> str:
    """Deterministic, sort-keys JSON. Treats None and {} identically."""
    if not params:
        return "{}"
    return json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)


def cache_key(endpoint: str, params: dict[str, Any] | None) -> str:
    """SHA256 hex of (endpoint, normalized params)."""
    payload = f"{endpoint}|{_stable_params_json(params)}".encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass
class DiskCache:
    """Content-addressed cache. Idempotent: never re-write the same key."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.root / "manifest.jsonl"
        self._lock = threading.Lock()

    def _path_for(self, key: str) -> Path:
        sub = self.root / key[:2]
        sub.mkdir(parents=True, exist_ok=True)
        return sub / f"{key}.json.gz"

    def has(self, key: str) -> bool:
        return self._path_for(key).exists()

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        with gzip.open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))

    def put(
        self,
        key: str,
        value: dict[str, Any],
        endpoint: str,
        params: dict[str, Any] | None,
        fetched_at: str,
    ) -> int:
        """Write value. No-op if key already exists. Returns bytes written (0 if no-op)."""
        path = self._path_for(key)
        if path.exists():
            return 0
        encoded = json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")
        with gzip.open(path, "wb") as f:
            f.write(encoded)
        bytes_on_disk = path.stat().st_size

        manifest_row = {
            "key": key,
            "endpoint": endpoint,
            "params": _stable_params_json(params),
            "fetched_at": fetched_at,
            "bytes": bytes_on_disk,
        }
        with self._lock:
            with self._manifest_path.open("a", encoding="utf-8") as mf:
                mf.write(json.dumps(manifest_row) + "\n")

        return bytes_on_disk

    def manifest_rows(self) -> list[dict[str, Any]]:
        """Read full manifest as list of dicts. Use sparingly on large caches."""
        if not self._manifest_path.exists():
            return []
        with self._manifest_path.open("r", encoding="utf-8") as mf:
            return [json.loads(line) for line in mf if line.strip()]
