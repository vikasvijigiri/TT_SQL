"""
Failure analysis report generator.

Reads the failure JSONL log produced by FailureTracker and generates a
ranked report of the most common failure patterns.  The report is suitable
for CI dashboards, release gates, and engineering retrospectives.

Usage::

    from agent.app.core.reporting.failure_report import generate_failure_report
    report = generate_failure_report(log_path="...failure_log.jsonl")
    print(report.summary())
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CategorySummary:
    category: str
    count: int
    percentage: float
    recent_questions: List[str] = field(default_factory=list)
    recent_errors: List[str] = field(default_factory=list)


@dataclass
class FailureReport:
    total_failures: int
    unique_categories: int
    top_categories: List[CategorySummary] = field(default_factory=list)
    most_failed_db: Optional[str] = None
    db_distribution: Dict[str, int] = field(default_factory=dict)
    generated_at: str = ""

    def summary(self) -> str:
        lines = [
            f"Failure Analysis Report - {self.total_failures} total failures",
            f"  Unique error categories : {self.unique_categories}",
            f"  Most affected database  : {self.most_failed_db or 'unknown'}",
            "",
            "  Top failure categories (ranked by frequency):",
        ]
        for cat in self.top_categories:
            lines.append(
                f"    [{cat.percentage:5.1f}%] {cat.category:30s}  ({cat.count} failures)"
            )
            if cat.recent_errors:
                lines.append(f"           Last error: {cat.recent_errors[-1][:120]}")
        return "\n".join(lines)

    def as_dict(self) -> Dict:
        return {
            "total_failures": self.total_failures,
            "unique_categories": self.unique_categories,
            "most_failed_db": self.most_failed_db,
            "db_distribution": self.db_distribution,
            "generated_at": self.generated_at,
            "top_categories": [
                {
                    "category": c.category,
                    "count": c.count,
                    "percentage": round(c.percentage, 2),
                    "recent_questions": c.recent_questions[-3:],
                    "recent_errors": c.recent_errors[-3:],
                }
                for c in self.top_categories
            ],
        }


def generate_failure_report(
    log_path: str | Path,
    top_n: int = 10,
    max_recent: int = 5,
) -> FailureReport:
    """
    Parse *log_path* (JSONL) and return a :class:`FailureReport`.

    Each line in the log must be a JSON object with at least
    ``error_category`` field (produced by FailureTracker).

    Parameters
    ----------
    log_path:
        Path to the JSONL failure log.
    top_n:
        How many top categories to include in the report.
    max_recent:
        Max recent examples per category.

    Returns
    -------
    FailureReport
        Always returns a valid object even if the log file does not exist
        or is empty.
    """
    from datetime import datetime

    log_path = Path(log_path)
    cat_counter: Counter = Counter()
    cat_questions: Dict[str, List[str]] = defaultdict(list)
    cat_errors: Dict[str, List[str]] = defaultdict(list)
    db_counter: Counter = Counter()
    total = 0

    if log_path.exists():
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    category = event.get("error_category", "unknown")
                    cat_counter[category] += 1
                    total += 1
                    q = event.get("question") or event.get("query") or ""
                    if q and len(cat_questions[category]) < max_recent:
                        cat_questions[category].append(str(q)[:200])
                    err = event.get("error") or event.get("error_msg") or ""
                    if err and len(cat_errors[category]) < max_recent:
                        cat_errors[category].append(str(err)[:200])
                    db = event.get("db_name") or event.get("database") or ""
                    if db:
                        db_counter[db] += 1
        except Exception:
            pass

    top_categories: List[CategorySummary] = []
    for cat, count in cat_counter.most_common(top_n):
        pct = (count / total * 100) if total else 0.0
        top_categories.append(
            CategorySummary(
                category=cat,
                count=count,
                percentage=pct,
                recent_questions=cat_questions[cat],
                recent_errors=cat_errors[cat],
            )
        )

    most_failed_db = db_counter.most_common(1)[0][0] if db_counter else None

    return FailureReport(
        total_failures=total,
        unique_categories=len(cat_counter),
        top_categories=top_categories,
        most_failed_db=most_failed_db,
        db_distribution=dict(db_counter.most_common(20)),
        generated_at=datetime.utcnow().isoformat() + "Z",
    )
