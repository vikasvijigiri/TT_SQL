"""
Per-query structured event log.

Records a snapshot of every completed pipeline execution:
  - ISO-8601 UTC timestamp
  - Question text (truncated to 500 chars)
  - Generated SQL (truncated to 2000 chars)
  - Total pipeline latency (seconds)
  - Success flag
  - Error message (if applicable)
  - LLM token count for the run

Events are held in a bounded in-memory deque (last ``memory_size`` events,
default 500) AND appended to a rolling JSONL file in ``resources/memory/``.
The file is pruned to ``file_max`` lines (default 1000) every 100 writes so
disk usage stays bounded even during long benchmark runs.

Usage::

    from agent.app.core.observability.query_analytics import record_query_event, get_analytics

    record_query_event(question="...", sql="...", latency_s=4.2, success=True)
    recent = get_analytics().get_recent(50)
"""

import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class QueryAnalytics:
    """
    Thread-safe rolling event store for pipeline query executions.
    Holds events in memory (fast reads) and persists to JSONL (durability).
    """

    def __init__(
        self,
        store_path: Path,
        memory_size: int = 500,
        file_max: int = 1000,
    ) -> None:
        self._store_path = store_path
        self._file_max = file_max
        self._lock = threading.Lock()
        self._buffer: deque[dict] = deque(maxlen=memory_size)
        self._write_count = 0
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        question: str,
        sql: str,
        latency_s: float,
        success: bool,
        error: Optional[str] = None,
        token_count: int = 0,
    ) -> None:
        """Append one query event to the in-memory buffer and the JSONL file."""
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": question[:500],
            "sql": sql[:2000],
            "latency_s": round(latency_s, 3),
            "success": success,
            "error": error,
            "token_count": token_count,
        }
        with self._lock:
            self._buffer.append(event)
            self._write_count += 1
            try:
                with self._store_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception:
                pass
            if self._write_count % 100 == 0:
                self._prune_file()

    def get_recent(self, n: int = 50) -> list[dict]:
        """Return the most recent ``n`` events, newest last."""
        with self._lock:
            events = list(self._buffer)
        return events[-n:]

    def stats(self) -> dict:
        """Aggregate stats over all in-memory events."""
        with self._lock:
            events = list(self._buffer)
        if not events:
            return {
                "total_in_memory": 0,
                "success_rate": None,
                "avg_latency_s": None,
                "error_count": 0,
            }
        total = len(events)
        success_count = sum(1 for e in events if e["success"])
        error_count = total - success_count
        avg_lat = sum(e["latency_s"] for e in events) / total
        return {
            "total_in_memory": total,
            "success_rate": round(success_count / total, 4),
            "avg_latency_s": round(avg_lat, 3),
            "error_count": error_count,
        }

    def _prune_file(self) -> None:
        """Trim the JSONL file to the last ``file_max`` lines."""
        try:
            if not self._store_path.exists():
                return
            lines = self._store_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if len(lines) > self._file_max:
                self._store_path.write_text(
                    "".join(lines[-self._file_max:]), encoding="utf-8"
                )
        except Exception:
            pass


# ── Module-level singleton ────────────────────────────────────────────────────
_analytics: Optional[QueryAnalytics] = None
_analytics_lock = threading.Lock()


def initialize(store_path: Path, memory_size: int = 500, file_max: int = 1000) -> None:
    """
    Configure the singleton.  Must be called once before ``record_query_event``.
    Idempotent: subsequent calls with the same path are no-ops.
    """
    global _analytics
    with _analytics_lock:
        if _analytics is None:
            _analytics = QueryAnalytics(store_path, memory_size, file_max)


def get_analytics() -> Optional[QueryAnalytics]:
    """Return the singleton, or None if not yet initialized."""
    return _analytics


def record_query_event(
    question: str,
    sql: str,
    latency_s: float,
    success: bool,
    error: Optional[str] = None,
    token_count: int = 0,
) -> None:
    """
    Record a completed pipeline execution.  Safe to call before ``initialize()``
    — events are silently dropped until the singleton is configured.
    """
    inst = _analytics
    if inst is not None:
        inst.record(question, sql, latency_s, success, error, token_count)
