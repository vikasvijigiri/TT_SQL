"""
Data quality auditor for query result sets.

Given the list of row-dicts returned by a successful SQL execution, computes
structural quality metrics and a composite quality score.

Metrics
-------
row_count     — number of rows returned
column_count  — number of distinct columns in the first row
null_rate     — fraction of all cells that contain None (0.0–1.0)
duplicate_rate — fraction of rows that are exact duplicates (0.0–1.0)
is_empty      — True when row_count == 0

Quality score
-------------
Starts at 1.0 and applies linear penalties:
  - 0.30 × null_rate        (high null-rate signals bad SQL returning unmapped columns)
  - 0.20 × duplicate_rate   (many duplicate rows often indicate a missing GROUP BY)
  - 0.50 immediate deduction when is_empty == True

Score is clamped to [0.0, 1.0] and rounded to 4 decimal places.
A score of 1.0 is ideal; anything below 0.5 should be flagged for human review.

``audit()`` is a pure stateless function.  A process-wide ``QualityMonitor``
singleton accumulates rolling quality scores across all executions and is
updated by the orchestrator via ``record_quality_event(csv_path)``.

Usage::

    from agent.app.core.observability.result_auditor import audit, get_quality_stats

    report = audit(rows)
    print(report.quality_score)   # 0.8750
    stats  = get_quality_stats()  # {"sample_count": 42, "avg_quality_score": 0.912, ...}
"""

from __future__ import annotations

import csv
import threading
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


# ── DataQualityReport ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DataQualityReport:
    """Immutable quality snapshot for one query result set."""

    row_count: int
    column_count: int
    null_rate: float       # fraction of cells that are None (0.0–1.0)
    duplicate_rate: float  # fraction of rows that are exact duplicates (0.0–1.0)
    is_empty: bool
    quality_score: float   # composite 0.0–1.0

    def as_dict(self) -> dict:
        return asdict(self)


_EMPTY_REPORT = DataQualityReport(
    row_count=0,
    column_count=0,
    null_rate=0.0,
    duplicate_rate=0.0,
    is_empty=True,
    quality_score=0.0,
)


def audit(rows: list[dict[str, Any]]) -> DataQualityReport:
    """
    Compute a ``DataQualityReport`` for *rows*.

    Parameters
    ----------
    rows:
        List of row dicts as returned by ``DatabaseExecutor.execute_direct()``.
        An empty list yields ``is_empty=True`` and ``quality_score=0.0``.
    """
    n = len(rows)
    if n == 0:
        return _EMPTY_REPORT

    columns: list[str] = list(rows[0].keys())
    col_count = len(columns)
    total_cells = n * col_count

    null_count = sum(1 for row in rows for val in row.values() if val is None)
    null_rate = round(null_count / total_cells, 4) if total_cells > 0 else 0.0

    frozen_rows = [tuple(row.get(c) for c in columns) for row in rows]
    unique_count = len(set(frozen_rows))
    duplicate_rate = round(1.0 - unique_count / n, 4)

    raw_score = 1.0 - (null_rate * 0.30) - (duplicate_rate * 0.20)
    quality_score = round(max(0.0, min(1.0, raw_score)), 4)

    return DataQualityReport(
        row_count=n,
        column_count=col_count,
        null_rate=null_rate,
        duplicate_rate=duplicate_rate,
        is_empty=False,
        quality_score=quality_score,
    )


# ── QualityMonitor — rolling quality score accumulator ───────────────────────

class QualityMonitor:
    """
    Thread-safe rolling accumulator of per-query quality scores.

    Maintains the last ``window_size`` quality scores and exposes rolling
    statistics (average, min, max, count below threshold).

    Parameters
    ----------
    window_size:
        Maximum number of quality scores to retain in memory.
    alert_threshold:
        Scores below this value are counted as quality alerts.
    """

    def __init__(
        self,
        window_size: int = 500,
        alert_threshold: float = 0.5,
    ) -> None:
        self._lock = threading.Lock()
        self._scores: deque[float] = deque(maxlen=window_size)
        self._alert_threshold = alert_threshold

    def record_score(self, score: float) -> None:
        """Append one quality score to the rolling window."""
        with self._lock:
            self._scores.append(score)

    def stats(self) -> dict:
        """Rolling quality statistics over the in-memory window."""
        with self._lock:
            scores = list(self._scores)
        if not scores:
            return {
                "sample_count": 0,
                "avg_quality_score": None,
                "min_quality_score": None,
                "max_quality_score": None,
                "below_threshold_count": 0,
                "alert_threshold": self._alert_threshold,
            }
        return {
            "sample_count": len(scores),
            "avg_quality_score": round(sum(scores) / len(scores), 4),
            "min_quality_score": round(min(scores), 4),
            "max_quality_score": round(max(scores), 4),
            "below_threshold_count": sum(1 for s in scores if s < self._alert_threshold),
            "alert_threshold": self._alert_threshold,
        }

    def reset(self) -> None:
        """Clear all scores.  Use in tests only."""
        with self._lock:
            self._scores.clear()


# ── Module-level singleton ────────────────────────────────────────────────────

_monitor = QualityMonitor()


def record_quality_score(score: float) -> None:
    """Record one quality score into the process-wide monitor."""
    _monitor.record_score(score)


def get_quality_stats() -> dict:
    """Return quality stats from the process-wide monitor."""
    return _monitor.stats()


def record_quality_event(csv_path: str) -> None:
    """
    Convenience helper for the orchestrator: read the result CSV at *csv_path*,
    audit it, and record the quality score into the process-wide monitor.

    Silently no-ops when the file does not exist or cannot be read.
    """
    try:
        p = Path(csv_path)
        if not p.exists():
            return
        with p.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows: list[dict[str, Any]] = list(reader)
        report = audit(rows)
        _monitor.record_score(report.quality_score)
    except Exception:
        pass
