"""Token-bucket rate limiter for Polygon (Massive) API.

Bootstraps conservatively at 4 req/min (5/min - 20% safety margin per
PROJECT_BRIEF.md). Calls `update_capacity()` after the first response
header read to raise the bucket to (observed_limit * 0.8).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    """Classic token bucket. Thread-safe.

    Args:
        capacity: max tokens (== max requests per refill window).
        refill_per_sec: tokens added per second (== capacity / 60 for per-minute).
        clock: optional monotonic-clock function (for testing).
    """

    capacity: float
    refill_per_sec: float

    def __post_init__(self) -> None:
        self._tokens: float = float(self.capacity)
        self._last: float = time.monotonic()
        self._lock = threading.Lock()
        self._clock = time.monotonic

    def _refill_locked(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            self._last = now

    def try_acquire(self, n: float = 1.0) -> bool:
        """Non-blocking acquire. True if a token was taken, False otherwise."""
        with self._lock:
            self._refill_locked()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    def acquire(self, n: float = 1.0, timeout: float | None = None) -> float:
        """Blocking acquire. Returns seconds waited.

        Raises TimeoutError if `timeout` elapses without acquiring.
        """
        deadline = None if timeout is None else self._clock() + timeout
        waited = 0.0
        while True:
            with self._lock:
                self._refill_locked()
                if self._tokens >= n:
                    self._tokens -= n
                    return waited
                # Time until enough tokens accrue.
                missing = n - self._tokens
                wait = missing / self.refill_per_sec if self.refill_per_sec > 0 else float("inf")

            if deadline is not None:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    raise TimeoutError(f"TokenBucket.acquire timed out after {timeout}s")
                wait = min(wait, remaining)

            time.sleep(max(wait, 0.001))
            waited += wait

    def update_capacity(self, new_capacity: float, new_refill_per_sec: float | None = None) -> None:
        """Resize the bucket (called after the first rate-limit header probe).

        New capacity takes effect immediately; current tokens are clamped to it.
        """
        with self._lock:
            self.capacity = float(new_capacity)
            if new_refill_per_sec is not None:
                self.refill_per_sec = float(new_refill_per_sec)
            self._tokens = min(self._tokens, self.capacity)

    def halve(self) -> None:
        """Halve capacity; call on 429. Logs loudly via caller."""
        with self._lock:
            self.capacity = max(1.0, self.capacity / 2.0)
            self.refill_per_sec = max(self.refill_per_sec / 2.0, 1.0 / 60.0)
            self._tokens = min(self._tokens, self.capacity)
