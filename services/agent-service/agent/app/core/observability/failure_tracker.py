"""

Structured failure event store.



Every failed pipeline execution is captured with its error message, the SQL

that was attempted, the question that triggered it, and a pre-classified error

category.  Events accumulate in a bounded in-memory deque (last 200 by default)

and are appended to a JSONL file in ``resources/memory/`` for post-mortem analysis.



Error categories

----------------

schema_error     - table or column does not exist

syntax_error     - invalid SQL token / parse failure

timeout          - query or LLM call exceeded time budget

type_error       - type mismatch or incompatible cast

permission_error - access denied at the database level

circuit_open     - LLM circuit breaker tripped

max_retries      - pipeline exhausted its correction loop

rate_limited     - rate-limiter or provider throttle fired

empty_result     - execution succeeded but DataIQ rejected empty output

unknown          - any error that did not match a known pattern



Usage::



    from agent.app.core.observability.failure_tracker import record_failure, get_failure_stats



    record_failure(question="...", sql="...", error="no such table: team")

    stats = get_failure_stats()   # {"total_in_memory": 1, "failure_groups": {"schema_error": 1}}

"""



import json

import threading

from collections import Counter, deque

from datetime import datetime, timezone

from pathlib import Path

from typing import Optional





# -- Error classification ------------------------------------------------------



_CATEGORY_KEYWORDS: dict[str, list[str]] = {

    "schema_error": [

        "no such table",

        "no such column",

        "ambiguous column",

        "table not found",

        "column not found",

        "unknown column",

        "does not exist",

    ],

    "syntax_error": [

        "syntax error",

        "parse error",

        "unexpected token",

        "near \"",

        "misuse of",

        "unrecognized token",

    ],

    "timeout": [

        "timeout",

        "timed out",

        "deadline exceeded",

        "cancelled",

        "operation canceled",

    ],

    "type_error": [

        "type mismatch",

        "cannot cast",

        "incompatible types",

        "wrong type",

        "invalid input syntax for type",

    ],

    "permission_error": [

        "permission denied",

        "access denied",

        "unauthorized",

        "insufficient privileges",

    ],

    "circuit_open": [

        "circuit breaker",

        "circuit open",

    ],

    "max_retries": [

        "max retries",

        "retries exceeded",

        "max retry",

    ],

    "rate_limited": [

        "rate limit",

        "too many requests",

        "throttled",

        "quota exceeded",

    ],

    "empty_result": [

        "data quality fail",

        "empty result",

        "no rows returned",

        "zero rows",

    ],

}





def _classify(error_msg: str) -> str:

    """Return the first matching error category, or 'unknown'."""

    lower = error_msg.lower()

    for category, keywords in _CATEGORY_KEYWORDS.items():

        if any(kw in lower for kw in keywords):

            return category

    return "unknown"





# -- FailureTracker class ------------------------------------------------------



class FailureTracker:

    """

    Thread-safe rolling failure store.



    Parameters

    ----------

    store_path:

        Optional path for the JSONL persistence file.  Set to None to run

        in-memory only (e.g. in tests).

    window_size:

        Maximum number of failure events to keep in memory.

    """



    def __init__(

        self,

        store_path: Optional[Path] = None,

        window_size: int = 200,

    ) -> None:

        self._store_path = store_path

        self._lock = threading.Lock()

        self._buffer: deque[dict] = deque(maxlen=window_size)

        if store_path is not None:

            store_path.parent.mkdir(parents=True, exist_ok=True)



    def record(

        self,

        question: str,

        sql: str,

        error: str,

        stage: str = "unknown",

    ) -> None:

        """Append one failure event to the in-memory buffer and JSONL file."""

        event = {

            "ts": datetime.now(timezone.utc).isoformat(),

            "question": question[:500],

            "sql": sql[:2000],

            "error": error[:1000],

            "category": _classify(error),

            "stage": stage,

        }

        with self._lock:

            self._buffer.append(event)

            if self._store_path is not None:

                try:

                    with self._store_path.open("a", encoding="utf-8") as fh:

                        fh.write(json.dumps(event) + "\n")

                except Exception:

                    pass



    def get_recent(self, n: int = 20) -> list[dict]:

        """Return the most recent ``n`` failure events, newest last."""

        with self._lock:

            return list(self._buffer)[-n:]



    def failure_groups(self) -> dict[str, int]:

        """Return a ``{category: count}`` dict, ordered by descending count."""

        with self._lock:

            events = list(self._buffer)

        return dict(Counter(e["category"] for e in events).most_common())



    def stats(self) -> dict:

        """Aggregate stats over the in-memory window."""

        with self._lock:

            events = list(self._buffer)

        return {

            "total_in_memory": len(events),

            "failure_groups": dict(Counter(e["category"] for e in events).most_common()),

        }





# -- Module-level singleton ----------------------------------------------------



_tracker: Optional[FailureTracker] = None

_tracker_lock = threading.Lock()





def initialize(

    store_path: Optional[Path] = None,

    window_size: int = 200,

) -> None:

    """

    Configure the process-wide singleton.  Must be called once before

    ``record_failure()``.  Idempotent: subsequent calls are no-ops.

    """

    global _tracker

    with _tracker_lock:

        if _tracker is None:

            _tracker = FailureTracker(store_path=store_path, window_size=window_size)





def get_tracker() -> Optional[FailureTracker]:

    """Return the singleton, or None if not yet initialized."""

    return _tracker





def record_failure(

    question: str,

    sql: str,

    error: str,

    stage: str = "unknown",

) -> None:

    """

    Record one pipeline failure.  Safe to call before ``initialize()`` - events

    are silently dropped until the singleton is configured.

    """

    inst = _tracker

    if inst is not None:

        inst.record(question, sql, error, stage)





def get_failure_stats() -> Optional[dict]:

    """Return aggregate failure stats, or None if not initialized."""

    inst = _tracker

    return inst.stats() if inst is not None else None

