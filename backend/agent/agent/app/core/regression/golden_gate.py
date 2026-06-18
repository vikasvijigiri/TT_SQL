"""
SQL regression gate — golden query suite.

Defines a set of known-good SQL queries against the IPL SQLite database with
structured invariants (row-count bounds, required columns, numeric value floors).
Run on demand to gate releases: if any golden case fails the build is blocked.

Design principles:
  - Invariants are intentionally range-based (not exact) to survive minor data
    variations while still catching structural regressions.
  - No LLM required — pure executor calls, runnable in CI without credentials.
  - Each case is independently skippable via ``enabled`` flag for environments
    without the IPL database.
  - The runner returns a structured report, not a boolean, so callers can
    render detailed failure diffs.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class GoldenCase:
    """A single regression test: SQL + invariants that must hold on its output."""

    name: str
    sql: str
    min_rows: int = 1
    max_rows: int = 100_000
    required_columns: list[str] = field(default_factory=list)
    value_assertions: list[dict] = field(default_factory=list)  # {column, min?, max?, eq?}
    enabled: bool = True


@dataclass
class CaseResult:
    name: str
    passed: bool
    rows_returned: int
    violations: list[str]
    error: Optional[str]
    sql: str


# ── Golden cases for the IPL SQLite database ──────────────────────────────────
GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        name="team_count",
        sql="SELECT count(*) AS cnt FROM team",
        min_rows=1,
        max_rows=1,
        required_columns=["cnt"],
        value_assertions=[{"column": "cnt", "min": 1}],
    ),
    GoldenCase(
        name="player_list",
        sql="SELECT player_id, player_name FROM player LIMIT 10",
        min_rows=1,
        max_rows=10,
        required_columns=["player_id", "player_name"],
    ),
    GoldenCase(
        name="top_scorers_three_table_join",
        sql="""
            SELECT p.player_name, SUM(bs.runs_scored) AS total_runs
            FROM batsman_scored bs
            JOIN ball_by_ball b
              ON bs.match_id=b.match_id AND bs.over_id=b.over_id
             AND bs.ball_id=b.ball_id   AND bs.innings_no=b.innings_no
            JOIN player p ON p.player_id=b.striker
            GROUP BY p.player_id, p.player_name
            ORDER BY total_runs DESC LIMIT 5
        """,
        min_rows=5,
        max_rows=5,
        required_columns=["player_name", "total_runs"],
        value_assertions=[{"column": "total_runs", "min": 1}],
    ),
    GoldenCase(
        name="match_win_margins",
        sql=(
            "SELECT match_id, win_margin FROM match "
            "WHERE win_margin IS NOT NULL ORDER BY win_margin DESC LIMIT 10"
        ),
        min_rows=1,
        max_rows=10,
        required_columns=["match_id", "win_margin"],
    ),
    GoldenCase(
        name="wicket_kinds",
        sql=(
            "SELECT kind_out, COUNT(*) AS cnt FROM wicket_taken "
            "GROUP BY kind_out ORDER BY cnt DESC"
        ),
        min_rows=1,
        max_rows=50,
        required_columns=["kind_out", "cnt"],
    ),
    GoldenCase(
        name="extra_runs_by_type",
        sql=(
            "SELECT extra_type, SUM(extra_runs) AS total FROM extra_runs "
            "GROUP BY extra_type ORDER BY total DESC"
        ),
        min_rows=1,
        max_rows=20,
        required_columns=["extra_type", "total"],
        value_assertions=[{"column": "total", "min": 1}],
    ),
    GoldenCase(
        name="player_match_roles",
        sql=(
            "SELECT role, COUNT(*) AS cnt FROM player_match "
            "GROUP BY role ORDER BY cnt DESC"
        ),
        min_rows=1,
        max_rows=10,
        required_columns=["role", "cnt"],
    ),
    GoldenCase(
        name="determinism_order_stability",
        sql="SELECT match_id, win_margin FROM match ORDER BY match_id LIMIT 20",
        min_rows=1,
        max_rows=20,
        required_columns=["match_id", "win_margin"],
    ),
]


class GoldenGate:
    """
    Runs the golden query suite against any DatabaseExecutor-compatible object
    and returns a structured pass/fail report.

    The executor must expose::

        execute_direct(sql: str) -> Tuple[bool, str, List[Dict]]
    """

    def __init__(self, cases: list[GoldenCase] | None = None) -> None:
        self._cases = cases if cases is not None else GOLDEN_CASES

    def run(self, executor: Any) -> dict:
        """
        Execute all enabled golden cases and return a report.

        Return value::

            {
                "passed": int,
                "failed": int,
                "skipped": int,
                "total": int,
                "all_passed": bool,
                "cases": List[CaseResult-as-dict],
            }
        """
        results: list[CaseResult] = []
        for case in self._cases:
            if not case.enabled:
                results.append(
                    CaseResult(
                        name=case.name,
                        passed=True,
                        rows_returned=0,
                        violations=[],
                        error=None,
                        sql=case.sql.strip(),
                    )
                )
                continue
            result = self._run_case(case, executor)
            results.append(result)

        passed = sum(1 for r in results if r.passed and r.error is None)
        failed = sum(1 for r in results if not r.passed or r.error is not None)
        skipped = sum(1 for c in self._cases if not c.enabled)

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": len(self._cases),
            "all_passed": failed == 0,
            "cases": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "rows_returned": r.rows_returned,
                    "violations": r.violations,
                    "error": r.error,
                }
                for r in results
            ],
        }

    @staticmethod
    def _run_case(case: GoldenCase, executor: Any) -> CaseResult:
        violations: list[str] = []
        try:
            ok, msg, rows = executor.execute_direct(case.sql.strip())
        except Exception as exc:
            return CaseResult(
                name=case.name,
                passed=False,
                rows_returned=0,
                violations=[],
                error=str(exc),
                sql=case.sql.strip(),
            )

        if not ok:
            return CaseResult(
                name=case.name,
                passed=False,
                rows_returned=0,
                violations=[],
                error=msg,
                sql=case.sql.strip(),
            )

        n = len(rows)

        if n < case.min_rows:
            violations.append(f"row count {n} < min {case.min_rows}")
        if n > case.max_rows:
            violations.append(f"row count {n} > max {case.max_rows}")

        if rows:
            actual_cols = set(rows[0].keys())
            for col in case.required_columns:
                if col not in actual_cols:
                    violations.append(f"required column '{col}' missing (got {sorted(actual_cols)})")

            for assertion in case.value_assertions:
                col = assertion["column"]
                if col not in actual_cols:
                    continue
                val = rows[0].get(col)
                if val is None:
                    violations.append(f"assertion column '{col}' is NULL in first row")
                    continue
                if "min" in assertion and val < assertion["min"]:
                    violations.append(f"'{col}' value {val} < expected min {assertion['min']}")
                if "max" in assertion and val > assertion["max"]:
                    violations.append(f"'{col}' value {val} > expected max {assertion['max']}")
                if "eq" in assertion and val != assertion["eq"]:
                    violations.append(f"'{col}' expected {assertion['eq']} but got {val}")

        return CaseResult(
            name=case.name,
            passed=len(violations) == 0,
            rows_returned=n,
            violations=violations,
            error=None,
            sql=case.sql.strip(),
        )
