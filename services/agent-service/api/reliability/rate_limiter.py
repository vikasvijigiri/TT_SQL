"""
Concurrent-query rate limiter (backpressure).

Uses a counting semaphore to cap in-flight queries.  When all slots are
occupied the caller receives a RuntimeError immediately - no queuing, no
blocking.  The endpoint translates this to HTTP 429 so clients can retry
with exponential back-off.

Configure via MAX_CONCURRENT_QUERIES env var (default: 10).

Usage::

    from api.reliability.rate_limiter import get_query_limiter

    limiter = get_query_limiter()
    try:
        with limiter.acquire():
            result = run_expensive_query(...)
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
"""

import os
import threading
from contextlib import contextmanager
from typing import Generator


class RateLimiter:
    """
    Semaphore-based concurrency cap.

    ``acquire()`` is a non-blocking context manager: it either takes a slot
    immediately or raises RuntimeError.  The slot is released when the
    ``with`` block exits, even on exception.
    """

    def __init__(self, max_concurrent: int) -> None:
        if max_concurrent < 1:
            raise ValueError(f"max_concurrent must be >= 1, got {max_concurrent}")
        self._max = max_concurrent
        self._sem = threading.Semaphore(max_concurrent)
        self._lock = threading.Lock()
        self._inflight = 0

    @contextmanager
    def acquire(self) -> Generator[None, None, None]:
        """
        Non-blocking slot acquisition.

        Raises RuntimeError if no slots are available (caller returns 429).
        Releases the slot on exit regardless of how the block terminates.
        """
        acquired = self._sem.acquire(blocking=False)
        if not acquired:
            raise RuntimeError(
                f"Concurrency limit reached ({self._max} queries in flight). "
                "Retry in a few seconds."
            )
        with self._lock:
            self._inflight += 1
        try:
            yield
        finally:
            with self._lock:
                self._inflight -= 1
            self._sem.release()

    @property
    def inflight(self) -> int:
        """Number of currently in-flight queries."""
        with self._lock:
            return self._inflight

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def available_slots(self) -> int:
        return max(0, self._max - self.inflight)

    def stats(self) -> dict:
        return {
            "max_concurrent": self._max,
            "inflight": self.inflight,
            "available_slots": self.available_slots,
        }


_MAX_CONCURRENT: int = int(os.getenv("MAX_CONCURRENT_QUERIES", "10"))

# Process-wide singleton - shared across all FastAPI worker threads
_query_limiter = RateLimiter(max_concurrent=_MAX_CONCURRENT)


def get_query_limiter() -> RateLimiter:
    """Return the process-wide rate limiter."""
    return _query_limiter
