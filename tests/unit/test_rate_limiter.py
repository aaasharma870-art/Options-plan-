"""Token bucket — known-answer tests, no `approx(self_output)`."""

from __future__ import annotations

import threading
import time

import pytest

from delta_optimizer.ingest.rate_limiter import TokenBucket


class TestTokenBucketBasics:

    def test_starts_full(self) -> None:
        b = TokenBucket(capacity=5, refill_per_sec=5.0)
        for _ in range(5):
            assert b.try_acquire() is True
        assert b.try_acquire() is False  # 6th call blocks

    def test_refill_after_wait(self) -> None:
        b = TokenBucket(capacity=2, refill_per_sec=10.0)  # refill 10/sec
        assert b.try_acquire(2) is True
        assert b.try_acquire() is False
        time.sleep(0.25)  # 0.25s × 10/sec = 2.5 tokens accrue, capped at 2
        assert b.try_acquire(2) is True

    def test_blocking_acquire_returns_wait_time(self) -> None:
        b = TokenBucket(capacity=1, refill_per_sec=4.0)  # one token per 0.25s
        b.try_acquire()  # drain
        t0 = time.monotonic()
        waited = b.acquire(1)
        elapsed = time.monotonic() - t0
        # We expect approximately 0.25s wait. Generous bounds for CI jitter.
        assert 0.15 <= elapsed <= 0.6
        assert waited > 0

    def test_acquire_timeout_raises(self) -> None:
        b = TokenBucket(capacity=1, refill_per_sec=0.1)  # one token per 10s
        b.try_acquire()
        with pytest.raises(TimeoutError):
            b.acquire(1, timeout=0.1)

    def test_update_capacity_clamps_tokens(self) -> None:
        b = TokenBucket(capacity=10, refill_per_sec=10.0)
        # Currently 10 tokens. Resize down to 3.
        b.update_capacity(3, new_refill_per_sec=3.0)
        assert b.capacity == 3.0
        assert b.refill_per_sec == 3.0
        # 3 tokens available; 4th should block (or be unavailable).
        assert b.try_acquire(3) is True
        assert b.try_acquire() is False

    def test_halve_on_429(self) -> None:
        b = TokenBucket(capacity=10, refill_per_sec=10.0)
        b.halve()
        assert b.capacity == 5.0
        # Refill rate halved too.
        assert b.refill_per_sec == 5.0
        b.halve()
        assert b.capacity == 2.5
        # Floor at 1.0.
        for _ in range(20):
            b.halve()
        assert b.capacity == 1.0

    def test_thread_safety_no_oversubscription(self) -> None:
        """20 threads racing for 5 tokens should hand out exactly 5."""
        b = TokenBucket(capacity=5, refill_per_sec=0.0)  # no refill during test
        successes: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            ok = b.try_acquire()
            with lock:
                successes.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(successes) == 5
