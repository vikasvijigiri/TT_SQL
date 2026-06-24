"""
Retrieval analytics tracker.

Records every BM25 few-shot retrieval call so the observability layer
can answer:

  - How often does the RAG service return useful examples?
  - Which databases are most frequently retrieved for?
  - What is the average number of results returned per query?

Thread-safe, in-process only.  Exposed via ``/api/analytics/retrieval``.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RetrievalAnalytics:
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)
    _total_calls: int = field(default=0)
    _hits: int = field(default=0)          # calls where >= 1 example returned
    _misses: int = field(default=0)        # calls where 0 examples returned
    _total_results: int = field(default=0) # sum of returned counts across all calls
    _db_calls: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record(self, db_name: str, n_results: int) -> None:
        with self._lock:
            self._total_calls += 1
            self._total_results += n_results
            self._db_calls[db_name] += 1
            if n_results > 0:
                self._hits += 1
            else:
                self._misses += 1

    def stats(self) -> Dict:
        with self._lock:
            total = self._total_calls
            avg = self._total_results / total if total else 0.0
            hit_rate = self._hits / total if total else None
            return {
                "total_retrieval_calls": total,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
                "avg_results_per_call": round(avg, 2),
                "db_distribution": dict(self._db_calls),
            }

    def reset(self) -> None:
        with self._lock:
            self._total_calls = 0
            self._hits = 0
            self._misses = 0
            self._total_results = 0
            self._db_calls.clear()


_tracker = RetrievalAnalytics()


def record_retrieval(db_name: str, n_results: int) -> None:
    """Record one BM25 retrieval call.  Never raises."""
    try:
        _tracker.record(db_name, n_results)
    except Exception:
        pass


def get_retrieval_stats() -> Dict:
    try:
        return _tracker.stats()
    except Exception:
        return {}


def reset_retrieval_analytics() -> None:
    _tracker.reset()
