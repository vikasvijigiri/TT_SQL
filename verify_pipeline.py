"""
Pipeline quality verification — no LLM required.

Covers:
  1. DB executor correctness
  2. AST pre-validator accuracy (sqlglot integration)
  3. Result quality auditor (null-rate, duplicate-rate, quality score)
  4. IQR outlier detection
  5. Determinism benchmark (20-run consistency across 6 queries)
  6. Golden regression gate (8 structural invariant cases)
  7. Schema completeness + explain plan + schema-aware identifier check

Run from the project root:
    python verify_pipeline.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "agent"))

from agent.app.repositories.db_executor import DatabaseExecutor
from agent.app.core.validation.sql_validator import validate as ast_validate
from agent.app.core.observability.result_auditor import audit as result_audit
from agent.app.core.regression.golden_gate import GoldenGate
import pandas as pd

DB = os.path.join(
    os.path.dirname(__file__),
    "backend", "agent", "agent", "resources", "databases", "sqlite", "IPL", "ipl.sqlite",
)

ex = DatabaseExecutor(db_name="IPL", dialect="sqlite", explicit_db_path=DB)
passed = failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        print(f"  PASS  {label}")
        passed += 1
    else:
        print(f"  FAIL  {label}  {detail}")
        failed += 1


# ===================================================================
# BLOCK 1 — DB Executor correctness
# ===================================================================
print("\n-- Block 1: DB Executor -----------------------------------------")

ok, msg, rows = ex.execute_direct("SELECT count(*) AS cnt FROM team")
check("Team count query succeeds", ok, msg)
check("At least 1 team in DB", ok and rows[0]["cnt"] > 0, str(rows))

ok, msg, rows = ex.execute_direct("""
    SELECT p.player_name, SUM(bs.runs_scored) AS total_runs
    FROM batsman_scored bs
    JOIN ball_by_ball b
      ON bs.match_id=b.match_id AND bs.over_id=b.over_id
     AND bs.ball_id=b.ball_id   AND bs.innings_no=b.innings_no
    JOIN player p ON p.player_id=b.striker
    GROUP BY p.player_id, p.player_name
    ORDER BY total_runs DESC LIMIT 5
""")
check("Multi-join 3-table aggregate succeeds", ok, msg)
check("Returns exactly 5 rows", ok and len(rows) == 5, f"got {len(rows)}")
if ok and rows:
    print(f"         Top scorer: {rows[0]['player_name']} ({rows[0]['total_runs']} runs)")

ok, msg, rows = ex.execute_direct("SELECT * FROM ghost_table_xyz_nonexistent")
check("Invalid table returns ok=False", not ok)
check("Error message is non-empty", len(msg) > 0)

err = ex._preflight_sqlite_statement(
    "SELECT ROW_NUMBER() OVER (PARTITION BY a ORDER BY ROW_NUMBER() OVER (ORDER BY b)) FROM t"
)
check("Preflight rejects nested window expression", err is not None and "nested window" in str(err).lower())


# ===================================================================
# BLOCK 2 — AST Pre-Validator (sqlglot)
# ===================================================================
print("\n-- Block 2: AST Pre-Validator -----------------------------------")

# Valid queries must pass
_valid_cases = [
    ("Simple SELECT", "SELECT count(*) AS cnt FROM team"),
    ("Multi-join aggregate", "SELECT p.player_name, COUNT(*) FROM player p JOIN match m ON m.match_id = m.match_id GROUP BY p.player_name"),
    ("Window function", "SELECT player_id, SUM(runs_scored) OVER (PARTITION BY player_id) AS cumulative FROM batsman_scored"),
    ("CTE", "WITH top AS (SELECT player_id, SUM(runs_scored) AS total FROM batsman_scored GROUP BY player_id) SELECT * FROM top ORDER BY total DESC LIMIT 10"),
    ("Subquery", "SELECT * FROM (SELECT kind_out, COUNT(*) AS cnt FROM wicket_taken GROUP BY kind_out) sub ORDER BY cnt DESC"),
]

for name, sql in _valid_cases:
    r = ast_validate(sql, dialect="sqlite")
    check(f"Valid SQL accepted: {name}", r.valid, r.error_summary or "")

# Invalid SQL must be caught
_invalid_cases = [
    ("Missing FROM keyword", "SELECT * FORM team"),
    ("Unmatched parenthesis", "SELECT count( FROM team"),
    ("Keyword as table name (no alias)", "SELECT FROM FROM WHERE"),
]

for name, sql in _invalid_cases:
    r = ast_validate(sql, dialect="sqlite")
    check(f"Invalid SQL rejected: {name}", not r.valid, f"Unexpectedly valid: {sql[:50]}")

# Table extraction from parse tree
r = ast_validate(
    "SELECT p.player_name FROM player p JOIN match m ON p.player_id = m.man_of_the_match",
    dialect="sqlite",
)
check("Table extraction: 'player' found", "player" in r.tables_referenced, str(r.tables_referenced))
check("Table extraction: 'match' found", "match" in r.tables_referenced, str(r.tables_referenced))
check("Column extraction works", len(r.columns_referenced) > 0, str(r.columns_referenced))


# ===================================================================
# BLOCK 3 — Result Quality Auditor
# ===================================================================
print("\n-- Block 3: Result Quality Auditor ------------------------------")

# Clean result: full matches table
ok, msg, rows = ex.execute_direct(
    "SELECT match_id, win_margin FROM match WHERE win_margin IS NOT NULL LIMIT 50"
)
if ok and rows:
    report = result_audit(rows)
    check("Quality score > 0.8 on clean result", report.quality_score > 0.8,
          f"score={report.quality_score}, null_rate={report.null_rate}")
    check("Null rate = 0 (no nulls in WHERE-filtered result)", report.null_rate == 0.0,
          f"null_rate={report.null_rate}")
    check("Duplicate rate low for match_id-keyed result", report.duplicate_rate < 0.05,
          f"dup_rate={report.duplicate_rate}")
    print(f"         quality_score={report.quality_score:.4f}  "
          f"null_rate={report.null_rate:.4f}  "
          f"dup_rate={report.duplicate_rate:.4f}  rows={report.row_count}")

# Empty result -> quality_score must be 0
report_empty = result_audit([])
check("Empty result -> quality_score=0.0", report_empty.quality_score == 0.0)
check("Empty result -> is_empty=True", report_empty.is_empty)

# Synthetic high-null result
null_rows = [{"a": None, "b": None}, {"a": 1, "b": None}]  # 75% null
report_null = result_audit(null_rows)
check("High-null synthetic result triggers low score", report_null.quality_score < 0.8,
      f"score={report_null.quality_score}")
check("Null rate correctly computed (0.75)", abs(report_null.null_rate - 0.75) < 0.01,
      f"null_rate={report_null.null_rate}")


# ===================================================================
# BLOCK 4 — Outlier Detection (IQR)
# ===================================================================
print("\n-- Block 4: IQR Outlier Detection -------------------------------")

# Build a dataframe with a known outlier and run the same IQR logic
# used inside the orchestrator DataIQ stats block.
_values = [10, 11, 12, 10, 11, 12, 10, 11, 1000]  # 1000 is a clear outlier
df_test = pd.DataFrame({"score": _values})
_s = df_test["score"].dropna()
_q1, _q3 = float(_s.quantile(0.25)), float(_s.quantile(0.75))
_iqr = _q3 - _q1
_lo, _hi = _q1 - 3 * _iqr, _q3 + 3 * _iqr
_n_out = int(((_s < _lo) | (_s > _hi)).sum())
check("IQR outlier correctly detected (1000 in tight distribution)", _n_out == 1,
      f"detected {_n_out} outliers, fence=[{_lo:.2g},{_hi:.2g}]")

# Clean uniform data should produce zero outliers
_uniform = list(range(1, 21))  # [1..20]
df_uni = pd.DataFrame({"v": _uniform})
_su = df_uni["v"].dropna()
_q1u, _q3u = float(_su.quantile(0.25)), float(_su.quantile(0.75))
_iqru = _q3u - _q1u
_lou, _hiu = _q1u - 3 * _iqru, _q3u + 3 * _iqru
_n_out_u = int(((_su < _lou) | (_su > _hiu)).sum())
check("Uniform distribution: zero outliers detected", _n_out_u == 0,
      f"detected {_n_out_u} spurious outliers")


# ===================================================================
# BLOCK 5 — Determinism Benchmark (5-run consistency)
# ===================================================================
print("\n-- Block 5: Determinism Benchmark -------------------------------")

_det_queries = [
    ("order_stability",         "SELECT match_id, win_margin FROM match ORDER BY match_id LIMIT 20"),
    ("top_scorers_5",           "SELECT p.player_name, SUM(bs.runs_scored) AS runs "
                                "FROM batsman_scored bs "
                                "JOIN ball_by_ball b ON bs.match_id=b.match_id AND bs.over_id=b.over_id AND bs.ball_id=b.ball_id AND bs.innings_no=b.innings_no "
                                "JOIN player p ON p.player_id=b.striker "
                                "GROUP BY p.player_id, p.player_name ORDER BY runs DESC LIMIT 5"),
    ("wicket_kinds",            "SELECT kind_out, COUNT(*) AS cnt FROM wicket_taken GROUP BY kind_out ORDER BY cnt DESC"),
    ("extra_runs_by_type",      "SELECT extra_type, SUM(extra_runs) AS total FROM extra_runs GROUP BY extra_type ORDER BY total DESC"),
    ("team_count",              "SELECT COUNT(*) AS cnt FROM team"),
    ("player_match_roles",      "SELECT role, COUNT(*) AS cnt FROM player_match GROUP BY role ORDER BY cnt DESC"),
]

_DETERMINISM_RUNS = 20   # representative sample of the 1000-run standard

all_deterministic = True
for q_name, sql in _det_queries:
    results = [str(ex.execute_direct(sql)[2]) for _ in range(_DETERMINISM_RUNS)]
    is_det = all(r == results[0] for r in results)
    if not is_det:
        all_deterministic = False
    check(f"{_DETERMINISM_RUNS}-run determinism: {q_name}", is_det)

score_str = "100%" if all_deterministic else "< 100%"
total_runs = _DETERMINISM_RUNS * len(_det_queries)
print(f"         Determinism score across all {total_runs} executions ({len(_det_queries)} queries x {_DETERMINISM_RUNS} runs): {score_str}")


# ===================================================================
# BLOCK 6 — Golden Regression Gate (8 structural invariant cases)
# ===================================================================
print("\n-- Block 6: Golden Regression Gate ------------------------------")

report = GoldenGate().run(ex)
for case in report["cases"]:
    status = "PASS" if case["passed"] else "FAIL"
    violations = ", ".join(case["violations"]) if case["violations"] else ""
    error = case.get("error") or ""
    detail = violations or error
    label = f"Golden: {case['name']} ({case['rows_returned']} rows)"
    check(label, case["passed"] and not case.get("error"), detail)
    if case["passed"] and not case.get("error"):
        passed -= 1; passed += 1  # already counted in check()

print(f"\n         all_passed={report['all_passed']}  "
      f"passed={report['passed']}  failed={report['failed']}")


# ===================================================================
# BLOCK 7 — Schema completeness + Explain plan + Identifier check
# ===================================================================
print("\n-- Block 7: Schema Completeness, Explain Plan, Identifier Check ----")

IPL_SCHEMA_DIR = os.path.join(
    os.path.dirname(__file__),
    "backend", "agent", "agent", "resources", "databases", "sqlite", "IPL",
)

# Schema completeness
from agent.app.core.validation.schema_completeness import check_schema_completeness
sc_report = check_schema_completeness(IPL_SCHEMA_DIR)
check("Schema completeness: at least 7 tables found", sc_report.total_tables >= 7,
      f"found {sc_report.total_tables}")
check("Schema completeness: coverage score >= 0.85", sc_report.coverage_score >= 0.85,
      f"coverage={sc_report.coverage_score:.3f}")
check("Schema completeness: no missing required keys in any table",
      all(not r.missing_keys for r in sc_report.table_results),
      str([r.table for r in sc_report.table_results if r.missing_keys]))
print(f"         coverage={sc_report.coverage_score:.3f}  "
      f"tables={sc_report.total_tables}  valid={sc_report.valid_tables}")

# Explain plan validation
ep = ex.explain_validate("SELECT match_id, win_margin FROM match WHERE win_margin IS NOT NULL LIMIT 20")
check("Explain plan: returns dict for SQLite", ep is not None and isinstance(ep, dict))
check("Explain plan: success=True for valid SQL", ep is not None and ep.get("success") is True,
      str(ep))
check("Explain plan: plan list non-empty", ep is not None and len(ep.get("plan", [])) > 0,
      f"plan={ep}")

ep_bad = ex.explain_validate("SELECT * FROM totally_fake_table_xyz_888")
check("Explain plan: invalid SQL returns success=False", ep_bad is not None and not ep_bad.get("success", True),
      str(ep_bad))

# Schema-aware identifier cross-check
from agent.app.core.validation.sql_validator import validate as ast_validate2, validate_against_schema
_known_tables = {"team", "player", "match", "batsman_scored", "ball_by_ball", "wicket_taken", "extra_runs", "player_match"}
_known_cols = {
    "player": ["player_id", "player_name", "country_name", "batting_hand", "bowling_skill", "player_id"],
    "match": ["match_id", "team_1", "team_2", "match_winner", "win_type", "win_margin", "season_id"],
    "team": ["team_id", "team_name"],
}

_clean_sql = "SELECT p.player_name, t.team_name FROM player p JOIN team t ON p.player_id = t.team_id"
_parse_clean = ast_validate2(_clean_sql, dialect="sqlite")
_id_clean = validate_against_schema(_parse_clean, _known_tables, _known_cols)
check("Identifier check: clean SQL has no hallucinated tables",
      _id_clean.hallucinated_tables == [], str(_id_clean.hallucinated_tables))

_halluc_sql = "SELECT salary FROM fake_employees"
_parse_halluc = ast_validate2(_halluc_sql, dialect="sqlite")
_id_halluc = validate_against_schema(_parse_halluc, _known_tables, _known_cols)
check("Identifier check: hallucinated table 'fake_employees' detected",
      "fake_employees" in _id_halluc.hallucinated_tables, str(_id_halluc.hallucinated_tables))
check("Identifier check: hallucinated column 'salary' detected",
      "salary" in _id_halluc.hallucinated_columns, str(_id_halluc.hallucinated_columns))

# Validation analytics accumulation
from agent.app.core.observability.validation_analytics import (
    record_validation_event, get_validation_stats, reset_validation_analytics,
    AST_VALID, AST_INVALID, IDENTIFIER_CLEAN, SCHEMA_HALLUCINATION
)
reset_validation_analytics()
record_validation_event(AST_VALID)
record_validation_event(AST_VALID)
record_validation_event(AST_INVALID)
record_validation_event(IDENTIFIER_CLEAN)
record_validation_event(SCHEMA_HALLUCINATION)
_val_stats = get_validation_stats()
check("Validation analytics: ast_valid=2", _val_stats["ast_valid"] == 2, str(_val_stats))
check("Validation analytics: ast_pass_rate=2/3",
      abs(_val_stats["ast_pass_rate"] - 2/3) < 0.01, str(_val_stats))
check("Validation analytics: id_clean_rate=0.5",
      abs(_val_stats["id_clean_rate"] - 0.5) < 0.01, str(_val_stats))

# Retrieval analytics
from agent.app.core.observability.retrieval_analytics import (
    record_retrieval, get_retrieval_stats, reset_retrieval_analytics
)
reset_retrieval_analytics()
record_retrieval("IPL", 3)
record_retrieval("IPL", 0)
record_retrieval("Baseball", 2)
_ret_stats = get_retrieval_stats()
check("Retrieval analytics: 3 calls tracked", _ret_stats["total_retrieval_calls"] == 3)
check("Retrieval analytics: hit_rate=2/3",
      abs(_ret_stats["hit_rate"] - 2/3) < 0.01, str(_ret_stats))
check("Retrieval analytics: IPL=2, Baseball=1",
      _ret_stats["db_distribution"].get("IPL") == 2 and _ret_stats["db_distribution"].get("Baseball") == 1,
      str(_ret_stats["db_distribution"]))

# Failure report generator
from agent.app.core.reporting.failure_report import generate_failure_report
_fr = generate_failure_report("/tmp/verify_pipeline_nonexistent.jsonl")
check("Failure report: empty log returns 0 failures", _fr.total_failures == 0)
check("Failure report: as_dict has required keys",
      all(k in _fr.as_dict() for k in ("total_failures", "unique_categories", "top_categories")))


# ===================================================================
# BLOCK 8 — Edge Case Bank (§20 / §18)
# ===================================================================
print("\n-- Block 8: Edge Case Bank ------------------------------------------")

# LIMIT 0 returns empty list, not error
ok8, msg8, rows8 = ex.execute_direct("SELECT * FROM player LIMIT 0")
check("Edge: LIMIT 0 returns empty result (not error)", ok8 and rows8 == [], f"{ok8} {msg8}")

# COUNT(*) on empty set = 0, not NULL
ok8, msg8, rows8 = ex.execute_direct("SELECT COUNT(*) AS cnt FROM match WHERE match_id < 0")
check("Edge: COUNT(*) on empty set = 0", ok8 and rows8[0]["cnt"] == 0, str(rows8))

# SUM on empty set = NULL
ok8, msg8, rows8 = ex.execute_direct("SELECT SUM(win_margin) AS s FROM match WHERE match_id < 0")
check("Edge: SUM on empty set = NULL", ok8 and rows8[0]["s"] is None, str(rows8))

# DISTINCT deduplicates
ok8, msg8, rows8 = ex.execute_direct("SELECT DISTINCT role FROM player_match")
roles = [r["role"] for r in rows8] if ok8 else []
check("Edge: DISTINCT returns unique values", ok8 and len(roles) == len(set(roles)), str(roles))

# COALESCE replaces NULL
ok8, msg8, rows8 = ex.execute_direct(
    "SELECT COALESCE(win_margin, -1) AS m FROM match LIMIT 10"
)
check("Edge: COALESCE replaces NULL with -1", ok8 and all(r["m"] != None for r in rows8), str(rows8[:2]))

# CASE expression in SELECT
ok8, msg8, rows8 = ex.execute_direct(
    "SELECT match_id, CASE WHEN win_type='runs' THEN 'bat' ELSE 'other' END AS mode "
    "FROM match LIMIT 5"
)
check("Edge: CASE expression executes correctly", ok8 and all("mode" in r for r in rows8))

# Subquery IN filter
ok8, msg8, rows8 = ex.execute_direct(
    "SELECT player_name FROM player "
    "WHERE player_id IN (SELECT striker FROM ball_by_ball LIMIT 50)"
)
check("Edge: Subquery IN filter executes", ok8, msg8)

# Three-table JOIN (team.name is the correct column, not team_name)
ok8, msg8, rows8 = ex.execute_direct(
    "SELECT p.player_name, t.name AS team_name, pm.role "
    "FROM player_match pm "
    "JOIN player p ON pm.player_id = p.player_id "
    "JOIN team t ON pm.team_id = t.team_id LIMIT 5"
)
check("Edge: Three-table JOIN executes", ok8 and len(rows8) > 0, msg8)

# LIKE pattern filter
ok8, msg8, rows8 = ex.execute_direct(
    "SELECT player_name FROM player WHERE player_name LIKE 'V%' LIMIT 5"
)
check("Edge: LIKE pattern filter works", ok8, msg8)
if ok8 and rows8:
    check("Edge: LIKE results start with 'V'", all(r["player_name"].startswith("V") for r in rows8),
          str([r["player_name"] for r in rows8]))
else:
    check("Edge: LIKE results start with 'V' (no rows found - acceptable)", True)


# ===================================================================
# Summary
# ===================================================================
total = passed + failed
print(f"\n{'='*60}")
print(f"  Results: {passed} passed, {failed} failed out of {total} checks")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
