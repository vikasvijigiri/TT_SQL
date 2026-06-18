"""
Thread-safe rolling-window latency tracker with SLA gate reporting.

Pattern: bounded deque → sort on demand → percentile index arithmetic.
The module singleton is shared across all orchestrator instances and worker
threads; callers record completions via `record_query_latency` and read the
current snapshot via `get_latency_stats`.
"""

import threading
from collections import deque

# SLA targets (seconds)
SLA_P50_S: float = 10.0
SLA_P95_S: float = 30.0
SLA_P99_S: float = 60.0


class LatencyTracker:
    """
    Maintains a bounded rolling window of query latency samples
    and computes P50/P95/P99 percentiles on demand.
    """

    def __init__(self, window_size: int = 1000) -> None:
        self._lock = threading.Lock()
        self._samples: deque[float] = deque(maxlen=window_size)

    def record(self, latency_s: float) -> None:
        with self._lock:
            self._samples.append(latency_s)

    @staticmethod
    def _percentile(p: float, sorted_samples: list[float]) -> float:
        n = len(sorted_samples)
        if n == 0:
            return 0.0
        idx = min(int(n * p / 100.0), n - 1)
        return sorted_samples[idx]

    def stats(self) -> dict:
        """Return P50/P95/P99 snapshot with SLA pass/fail flags."""
        with self._lock:
            samples = list(self._samples)

        if not samples:
            return {
                "sample_count": 0,
                "p50_s": None,
                "p95_s": None,
                "p99_s": None,
                "mean_s": None,
                "sla": {
                    "p50_ok": None,
                    "p95_ok": None,
                    "p99_ok": None,
                    "targets": {
                        "p50_s": SLA_P50_S,
                        "p95_s": SLA_P95_S,
                        "p99_s": SLA_P99_S,
                    },
                },
            }

        sorted_s = sorted(samples)
        n = len(sorted_s)
        p50 = self._percentile(50, sorted_s)
        p95 = self._percentile(95, sorted_s)
        p99 = self._percentile(99, sorted_s)
        mean = sum(sorted_s) / n

        return {
            "sample_count": n,
            "p50_s": round(p50, 3),
            "p95_s": round(p95, 3),
            "p99_s": round(p99, 3),
            "mean_s": round(mean, 3),
            "sla": {
                "p50_ok": p50 <= SLA_P50_S,
                "p95_ok": p95 <= SLA_P95_S,
                "p99_ok": p99 <= SLA_P99_S,
                "targets": {
                    "p50_s": SLA_P50_S,
                    "p95_s": SLA_P95_S,
                    "p99_s": SLA_P99_S,
                },
            },
        }

    @property
    def sample_count(self) -> int:
        with self._lock:
            return len(self._samples)


# Process-wide singleton — shared across all threads and orchestrator instances
_pipeline_tracker = LatencyTracker(window_size=1000)


def record_query_latency(latency_s: float) -> None:
    """Record a completed query latency (seconds). Call at every execute_query exit."""
    _pipeline_tracker.record(latency_s)


def get_latency_stats() -> dict:
    """Return current P50/P95/P99 stats and SLA pass/fail status."""
    return _pipeline_tracker.stats()
