"""
Passive determinism score tracker.

For every completed pipeline execution the question text and generated SQL are
hashed and stored.  When the same question is seen a second time the tracker
compares the new SQL hash to the one stored from the previous invocation and
records a match/mismatch.  The rolling determinism score is the fraction of
same-question comparisons that produced identical SQL.

A score of 100.0 means every repeated question always produced the same SQL
output — the ideal for a production Text-to-SQL system.  A dip below 95.0 is
a signal to investigate LLM temperature settings or prompt non-determinism.

The tracker uses MD5 for speed (not security); collision risk on this volume
of data is negligible.

Usage::

    from agent.app.core.observability.determinism_tracker import record, get_determinism_stats

    record(question="How many teams?", sql="SELECT COUNT(*) FROM team")
    stats = get_determinism_stats()
    # {"total_comparisons": 0, "determinism_score": None, "matched": 0, "mismatched": 0}
"""

import hashlib
import threading
from collections import deque


class DeterminismTracker:
    """
    Thread-safe passive determinism tracker.

    Internally maintains two data structures:
    - ``_sql_by_question`` dict: maps each question hash to the *last* SQL hash
      seen for that question.  When the same question arrives again, the new
      SQL hash is compared to the stored one, and the result (True/False) is
      appended to the rolling comparison window.
    - ``_comparisons`` deque: bounded rolling window of boolean match results
      used to compute the determinism score.

    Parameters
    ----------
    window_size:
        Maximum number of per-question comparisons to keep in the rolling window.
        Does not bound the number of unique questions tracked.
    """

    def __init__(self, window_size: int = 200) -> None:
        self._lock = threading.Lock()
        self._sql_by_question: dict[str, str] = {}
        self._comparisons: deque[bool] = deque(maxlen=window_size)

    @staticmethod
    def _hash_question(text: str) -> str:
        """Case- and whitespace-normalised question hash."""
        return hashlib.md5(text.strip().lower().encode()).hexdigest()

    @staticmethod
    def _hash_sql(sql: str) -> str:
        """Whitespace-normalised SQL hash."""
        return hashlib.md5(sql.strip().encode()).hexdigest()

    def record(self, question: str, sql: str) -> None:
        """
        Record one completed query execution.

        If this is the first time the question is seen, the SQL hash is stored
        and no comparison is recorded.  On all subsequent calls with the same
        question a match/mismatch comparison is appended to the rolling window
        and the stored SQL hash is updated to the latest value.
        """
        q_hash = self._hash_question(question)
        s_hash = self._hash_sql(sql)
        with self._lock:
            prev = self._sql_by_question.get(q_hash)
            self._sql_by_question[q_hash] = s_hash
            if prev is not None:
                self._comparisons.append(prev == s_hash)

    def stats(self) -> dict:
        """
        Return determinism statistics over the rolling comparison window.

        Return value::

            {
                "total_comparisons": int,         # number of repeat-question pairs seen
                "determinism_score": float | None, # 0.0–100.0; None before first comparison
                "matched": int,
                "mismatched": int,
                "unique_questions_seen": int,
            }
        """
        with self._lock:
            comparisons = list(self._comparisons)
            unique = len(self._sql_by_question)

        total = len(comparisons)
        if total == 0:
            return {
                "total_comparisons": 0,
                "determinism_score": None,
                "matched": 0,
                "mismatched": 0,
                "unique_questions_seen": unique,
            }

        matched = sum(comparisons)
        return {
            "total_comparisons": total,
            "determinism_score": round(matched / total * 100, 2),
            "matched": matched,
            "mismatched": total - matched,
            "unique_questions_seen": unique,
        }

    def reset(self) -> None:
        """Clear all state.  Intended for test isolation only."""
        with self._lock:
            self._sql_by_question.clear()
            self._comparisons.clear()


# ── Module-level singleton ────────────────────────────────────────────────────

_tracker = DeterminismTracker()


def record(question: str, sql: str) -> None:
    """Record one completed query execution into the process-wide tracker."""
    _tracker.record(question, sql)


def get_determinism_stats() -> dict:
    """Return determinism stats from the process-wide tracker."""
    return _tracker.stats()


def reset() -> None:
    """Reset the process-wide tracker.  Use in tests only."""
    _tracker.reset()
