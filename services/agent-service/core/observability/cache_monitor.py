"""
Cache hit-rate monitor.

Industry-standard pattern: named counters with a process-wide registry.
Callers register a monitor by name (`get_or_create`), record hits and misses
explicitly or via the `monitored` decorator, and read aggregate stats from
`all_stats()` for health/observability endpoints.
"""

import threading
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class CacheMonitor:
    """Thread-safe hit/miss counter for a single named cache."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def record_hit(self) -> None:
        with self._lock:
            self._hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self._misses += 1

    @property
    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "name": self.name,
                "hits": self._hits,
                "misses": self._misses,
                "total": total,
                "hit_rate": round(self._hits / total, 4) if total > 0 else None,
            }

    def reset(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0


# Process-wide registry - keyed by cache name
_registry: dict[str, CacheMonitor] = {}
_registry_lock = threading.Lock()


def get_or_create(name: str) -> CacheMonitor:
    """Return (or create) the monitor for `name`."""
    with _registry_lock:
        if name not in _registry:
            _registry[name] = CacheMonitor(name)
        return _registry[name]


def all_stats() -> list[dict]:
    """Return a snapshot of stats for every registered monitor."""
    with _registry_lock:
        return [m.stats for m in _registry.values()]


def monitored(name: str) -> Callable[[F], F]:
    """
    Decorator factory that wraps a function (assumed to use an internal cache)
    and records a miss on every call.

    Usage: decorate the *inner* (uncached) function and pair it with explicit
    `record_hit()` calls in the calling code when a cache hit is detected.
    Alternatively, wrap the outer (cached) function and call `record_miss`
    only when the underlying computation actually runs, using a sentinel.
    """

    def decorator(fn: F) -> F:
        monitor = get_or_create(name)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            monitor.record_miss()
            return fn(*args, **kwargs)

        wrapper.__name__ = fn.__name__  # type: ignore[attr-defined]
        wrapper.__doc__ = fn.__doc__    # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
