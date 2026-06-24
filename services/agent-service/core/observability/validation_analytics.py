"""
Validation analytics tracker.

Records the outcome of every SQL validation event (AST parse, schema
identifier cross-check, explain plan, preflight) so the observability
layer can answer:

  - What fraction of generated SQL passes AST validation on the first try?
  - Which error categories appear most often?
  - Are hallucinated column/table references improving or getting worse?

Thread-safe, in-process only (no persistence).  Exposed via
``/api/analytics/validation``.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional

# --- event types ---------------------------------------------------------

AST_VALID = "ast_valid"
AST_INVALID = "ast_invalid"
SCHEMA_HALLUCINATION = "schema_hallucination"
EXPLAIN_WARNING = "explain_warning"
PREFLIGHT_REJECTION = "preflight_rejection"
IDENTIFIER_CLEAN = "identifier_clean"


@dataclass
class ValidationAnalytics:
    """Accumulates validation counters in a thread-safe way."""

    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)
    _counters: Dict[str, int] = field(default_factory=lambda: defaultdict(int), compare=False)
    _error_categories: Dict[str, int] = field(default_factory=lambda: defaultdict(int), compare=False)

    def record(self, event_type: str, error_category: Optional[str] = None) -> None:
        with self._lock:
            self._counters[event_type] += 1
            if error_category:
                self._error_categories[error_category] += 1

    def stats(self) -> Dict:
        with self._lock:
            counters = dict(self._counters)
            categories = dict(self._error_categories)

        total_ast = counters.get(AST_VALID, 0) + counters.get(AST_INVALID, 0)
        ast_pass_rate = counters.get(AST_VALID, 0) / total_ast if total_ast else None

        total_id = counters.get(IDENTIFIER_CLEAN, 0) + counters.get(SCHEMA_HALLUCINATION, 0)
        id_clean_rate = counters.get(IDENTIFIER_CLEAN, 0) / total_id if total_id else None

        return {
            "ast_valid": counters.get(AST_VALID, 0),
            "ast_invalid": counters.get(AST_INVALID, 0),
            "ast_pass_rate": round(ast_pass_rate, 4) if ast_pass_rate is not None else None,
            "schema_hallucinations_detected": counters.get(SCHEMA_HALLUCINATION, 0),
            "identifier_clean_passes": counters.get(IDENTIFIER_CLEAN, 0),
            "id_clean_rate": round(id_clean_rate, 4) if id_clean_rate is not None else None,
            "explain_plan_warnings": counters.get(EXPLAIN_WARNING, 0),
            "preflight_rejections": counters.get(PREFLIGHT_REJECTION, 0),
            "error_categories": categories,
        }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._error_categories.clear()


# Module-level singleton
_tracker = ValidationAnalytics()


def record_validation_event(event_type: str, error_category: Optional[str] = None) -> None:
    """Record a single validation event.  Never raises."""
    try:
        _tracker.record(event_type, error_category)
    except Exception:
        pass


def get_validation_stats() -> Dict:
    """Return current validation analytics stats."""
    try:
        return _tracker.stats()
    except Exception:
        return {}


def reset_validation_analytics() -> None:
    """Reset all counters (for tests)."""
    _tracker.reset()
