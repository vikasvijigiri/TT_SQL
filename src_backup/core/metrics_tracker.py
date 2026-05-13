"""
MetricsTracker
==============
Captures meaningful, analysis-ready per-instance pipeline metrics and upserts
them into: results/pipeline_metrics.csv

Design philosophy
-----------------
Every column answers a concrete question a researcher or engineer would ask:
  - "Where does the pipeline break for hard queries?"
  - "What is the cost per instance for this model?"
  - "Does schema complexity predict failure?"
  - "How many retries does a HIGH-complexity query need?"

Thread-safe for parallel batch execution.
"""

import csv
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import RESULTS_BASE_DIR

_write_lock = threading.Lock()

def _metrics_path(db_name: str) -> Path:
    """Per-DB metrics file: results/{db_name}/metrics.csv"""
    return RESULTS_BASE_DIR / db_name / "metrics.csv"

# Keep a module-level alias for the backfill script to import
METRICS_CSV = None  # not used — per-DB now

# ── Column definitions ─────────────────────────────────────────────────────────
COLUMNS = [
    # 1. Identity
    "id",           # Spider 2.0 instance ID
    "db",           # Database name
    "dialect",      # sqlite | bigquery | snowflake | postgres
    "model",        # LLM model identifier
    "ts",           # ISO-8601 completion timestamp

    # 2. Outcome
    "status",       # SUCCESS | FAILED | ERROR
    "rows_out",     # Result rows returned (0 = likely wrong)
    "cols_out",     # Result columns returned
    "has_data",     # 1 if ≥1 meaningful data row in output CSV

    # 3. Timing
    "duration_s",   # Total pipeline wall-clock seconds
    "exec_ms",      # DB execution time (ms)
    "llm_s",        # LLM time estimate (duration_s - exec_ms/1000)

    # 4. Question Profile
    "q_type",       # AGGREGATION | LOOKUP | RANKING | MULTI_HOP | ...
    "q_lvl",        # LOW | MEDIUM | HIGH (agent-assessed)
    "ext_kb",       # 1 if external knowledge file was supplied

    # 5. Database Profile
    "db_tables",    # Total tables in the DB
    "fk_density",   # FK relations / tables (DB interconnectedness)
    "schema_cols",  # Total columns across all tables
    "tbl_used",     # Tables selected by TableSelectorAgent
    "tbl_cov",      # tbl_used / db_tables ratio
    "cache_hit",    # 1 if schema was served from metadata cache

    # 6. SQL Generation
    "iters",        # Builder-Critic loop iteration count
    "first_pass",   # 1 if critic passed on first attempt
    "retried",      # 1 if >1 iteration was needed
    "critic_rej",   # Count of Critic rejections
    "exec_errs",    # Count of execution errors during retries
    "sql_approach", # CTE | SUBQUERY | INLINE | TEMP_TABLE

    # 7. SQL Structure
    "sql_score",    # Composite complexity 0–8
    "joins",        # JOIN count in final SQL
    "has_cte",      # 1 if WITH clause present
    "has_wfn",      # 1 if OVER/PARTITION BY present
    "has_subq",     # 1 if nested SELECT present
    "has_agg",      # 1 if SUM/COUNT/AVG/MIN/MAX present
    "has_case",     # 1 if CASE WHEN present
    "sql_lines",    # Line count of final SQL

    # 8. Failure
    "fail_stage",   # none | planning | table_select | generation | execution | fatal
    "err_cat",      # none | syntax_error | runtime_error | empty_result | critic_rejected | ...
    "err_msg",      # First 300 chars of last error

    # 9. Cost
    "tok_in",       # Cumulative prompt tokens
    "tok_out",      # Cumulative completion tokens
    "tok_total",    # tok_in + tok_out
    "cost_usd",     # Estimated cost in USD
    "cost_per_row", # cost_usd / rows_out
]


# ── Model cost table (price per 1M tokens, input/output) ──────────────────────
# Approximate rates for common model families
_MODEL_COST_TABLE = {
    "gpt-4o":                   (5.00,  15.00),
    "gpt-4":                    (30.00, 60.00),
    "gpt-3.5":                  (0.50,  1.50),
    "claude-3-5-sonnet":        (3.00,  15.00),
    "claude-3-haiku":           (0.25,  1.25),
    "claude-3-opus":            (15.00, 75.00),
    "gpt-oss-safeguard-120b":   (2.00,  6.00),   # bedrock custom proxy
    "nova-pro":                 (0.80,  3.20),
    "nova-lite":                (0.06,  0.24),
    "llama":                    (0.20,  0.60),
    "mistral":                  (0.20,  0.60),
}
_DEFAULT_COST = (1.00, 3.00)  # fallback $/1M tokens


def _model_cost(model_name: str, tok_in: int, tok_out: int) -> float:
    """Estimate USD cost from token counts and model name."""
    cost_in_pm, cost_out_pm = _DEFAULT_COST
    model_lower = (model_name or "").lower()
    for key, rates in _MODEL_COST_TABLE.items():
        if key in model_lower:
            cost_in_pm, cost_out_pm = rates
            break
    return round((tok_in * cost_in_pm + tok_out * cost_out_pm) / 1_000_000, 6)


# ── Question type classifier (rule-based) ─────────────────────────────────────
_TYPE_PATTERNS = [
    ("RANKING",      [r"\b(top|bottom|rank|ranking|highest|lowest|most|least|n-th)\b"]),
    ("TIME_SERIES",  [r"\b(month|year|quarter|date|daily|weekly|trend|over time|between \d{4})\b"]),
    ("COMPARISON",   [r"\b(compar|versus|vs\.?|differ|more than|less than|greater|higher|lower)\b"]),
    ("CALCULATION",  [r"\b(calculat|sum|total|average|avg|median|percent|ratio|rate|formula)\b"]),
    ("AGGREGATION",  [r"\b(count|how many|number of|group by|per|each)\b"]),
    ("MULTI_HOP",    [r"\b(join|relat|connect|link|through|via|for each .* their|associ)\b"]),
    ("LOOKUP",       [r"\b(what is|what are|find|list|show|return|get|name of|who)\b"]),
]


def _classify_question(question: str, intent_joins: list) -> str:
    q = (question or "").lower()
    for label, pats in _TYPE_PATTERNS:
        if any(re.search(p, q) for p in pats):
            return label
    if intent_joins:
        return "MULTI_HOP"
    return "MIXED"


# ── SQL complexity score (composite 0–8) ──────────────────────────────────────
def _sql_complexity(sql: str) -> int:
    if not sql:
        return 0
    score = 0
    joins = len(re.findall(r"\bJOIN\b", sql, re.IGNORECASE))
    score += min(joins * 1, 2)  # up to 2 pts for joins
    if re.search(r"\bWITH\b", sql, re.IGNORECASE):               score += 1
    if re.search(r"\bOVER\s*\(", sql, re.IGNORECASE):            score += 2  # window fns hardest
    if re.search(r"\(\s*SELECT\b", sql, re.IGNORECASE):          score += 1
    if re.search(r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(", sql, re.IGNORECASE): score += 1
    if re.search(r"\bCASE\s+WHEN\b", sql, re.IGNORECASE):        score += 1
    return min(score, 8)


def _kw(sql: str, *patterns: str) -> int:
    for p in patterns:
        if re.search(rf"\b{p}\b", sql or "", re.IGNORECASE):
            return 1
    return 0


def _join_count(sql: str) -> int:
    return len(re.findall(r"\bJOIN\b", sql or "", re.IGNORECASE))


def _fk_density(schema: dict) -> float:
    tables = len(schema)
    if not tables:
        return 0.0
    total_fk = sum(len(m.get("foreign_keys", [])) for m in schema.values())
    return round(total_fk / tables, 2)


def _total_columns(schema: dict) -> int:
    return sum(len(m.get("columns", [])) for m in schema.values())


# ── Error classification ───────────────────────────────────────────────────────
def _classify_error(
    pipeline_status: str,
    exec_errors: list,
    feedback_hist: list,
    is_result_valid: bool,
    error_msg: str,
    has_data: bool,
    state_step: str,
) -> tuple[str, str]:
    """Returns (failure_stage, error_category)."""
    if pipeline_status == "SUCCESS":
        return "none", "none"

    msg = (error_msg or "").lower()

    # Stage: where in the pipeline did it go wrong
    step = (state_step or "").lower()
    if "executor" in step or exec_errors:
        stage = "execution"
    elif feedback_hist and not is_result_valid:
        stage = "generation"
    elif "tableselector" in step or "context" in step:
        stage = "table_select"
    elif "planner" in step:
        stage = "planning"
    elif pipeline_status == "ERROR":
        stage = "fatal"
    else:
        stage = "execution"  # most FAILED with no data are execution-stage

    # Category: why
    if "syntax" in msg or "parse error" in msg or "invalid sql" in msg:
        category = "syntax_error"
    elif "timeout" in msg or "timed out" in msg:
        category = "timeout"
    elif "no such table" in msg or "column" in msg and "not found" in msg:
        category = "schema_mismatch"
    elif pipeline_status == "ERROR":
        category = "fatal_crash"
    elif not has_data and not exec_errors:
        category = "empty_result"
    elif exec_errors:
        category = "runtime_error"
    elif feedback_hist and not is_result_valid:
        category = "critic_rejected"
    else:
        category = "unknown"

    return stage, category


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _ensure_header(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writeheader()


def _load_existing(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # support both old 'instance_id' header and new 'id' header
            key = row.get("id") or row.get("instance_id", "")
            if key:
                rows[key] = row
    return rows


# ── Public API ────────────────────────────────────────────────────────────────

def extract_and_write(
    state: Any,
    is_fatal: bool,
    pipeline_status: str,
    has_data: bool,
    pipeline_duration_s: float = 0.0,
    error_message: str | None = None,
) -> None:
    """
    Extract metrics from a completed AgentState and upsert into pipeline_metrics.csv.

    Parameters
    ----------
    state               : AgentState (may be None on hard crash)
    is_fatal            : bool
    pipeline_status     : 'SUCCESS' | 'FAILED' | 'ERROR'
    has_data            : bool – output CSV has ≥1 meaningful row
    pipeline_duration_s : total wall-clock seconds for the run
    error_message       : last error string (supplement AgentState)
    """
    if state is None:
        return

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Schema & DB Profile ────────────────────────────────────────────────────
    full_schema = getattr(state, "full_schema_info", {}) or {}
    sel_schema  = getattr(state, "schema_info",      {}) or {}
    rel_tables  = getattr(state, "relevant_tables",  []) or []

    db_tables    = len(full_schema)
    tables_used  = len(rel_tables)
    fk_density   = _fk_density(full_schema)
    schema_size  = _total_columns(full_schema)
    cov_ratio    = round(tables_used / db_tables, 4) if db_tables else 0.0
    cache_hit    = 1 if (full_schema and not getattr(state, "_schema_was_fetched", False)) else 0

    # ── Question ───────────────────────────────────────────────────────────────
    question       = state.user_query or ""
    intent_joins   = [] # intent_joins removed from state; keeping empty list for compat
    question_type  = _classify_question(question, intent_joins)
    complexity     = getattr(state, "complexity_score",   "MEDIUM") or "MEDIUM"

    # ── Generation ─────────────────────────────────────────────────────────────
    final_sql      = getattr(state, "chosen_query",               "") or ""
    iter_count     = getattr(state, "iteration_count",            0)  or 0
    exec_errors    = getattr(state, "execution_error_history",    []) or []
    feedback_hist  = getattr(state, "feedback_history",           []) or []
    candidates     = getattr(state, "sql_candidates",          []) or []
    is_valid       = getattr(state, "is_result_valid",            False)
    current_step   = getattr(state, "current_step",               "") or ""

    sql_approach = ""
    if candidates:
        sql_approach = getattr(candidates[-1], "approach", "") or ""

    # ── Execution ──────────────────────────────────────────────────────────────
    exec_result   = getattr(state, "execution_result", None)
    result_rows   = 0
    result_cols   = 0
    sql_exec_ms   = 0.0
    if exec_result:
        result_rows = getattr(exec_result, "row_count",          0)   or 0
        result_cols = len(getattr(exec_result, "columns",        []))
        sql_exec_ms = round(getattr(exec_result, "execution_time_ms", 0.0), 2)

    llm_time_est = round(max(0.0, pipeline_duration_s - sql_exec_ms / 1000), 3)

    # ── Error ──────────────────────────────────────────────────────────────────
    last_err = error_message or ""
    if not last_err:
        if exec_errors:           last_err = exec_errors[-1]
        elif getattr(state, "error_message", None): last_err = state.error_message or ""

    failure_stage, error_category = _classify_error(
        pipeline_status, exec_errors, feedback_hist, is_valid,
        last_err, has_data, current_step,
    )

    # ── SQL Structural Profile ─────────────────────────────────────────────────
    sql_complexity  = _sql_complexity(final_sql)
    sql_joins       = _join_count(final_sql)
    sql_cte         = _kw(final_sql, "WITH")
    sql_window      = 1 if re.search(r"\bOVER\s*\(", final_sql or "", re.IGNORECASE) else 0
    sql_subq        = 1 if re.search(r"\(\s*SELECT\b", final_sql or "", re.IGNORECASE) else 0
    sql_agg         = _kw(final_sql, "SUM", "COUNT", "AVG", "MIN", "MAX")
    sql_case        = _kw(final_sql, "CASE")
    sql_lines       = len((final_sql or "").splitlines())

    # ── Tokens & Cost ──────────────────────────────────────────────────────────
    token_usage   = getattr(state, "token_usage", {}) or {}
    tok_in        = token_usage.get("input",  0)
    tok_out       = token_usage.get("output", 0)
    tok_total     = tok_in + tok_out
    model_name    = getattr(state, "model_name", "") or ""
    cost_usd      = _model_cost(model_name, tok_in, tok_out)
    cost_per_row  = round(cost_usd / result_rows, 6) if result_rows > 0 else 0.0

    row = {
        # 1. Identity
        "id":           state.instance_id,
        "db":           state.db_name or "",
        "dialect":      getattr(state, "dialect", "sqlite"),
        "model":        model_name,
        "ts":           now_utc,

        # 2. Outcome
        "status":       pipeline_status,
        "rows_out":     result_rows,
        "cols_out":     result_cols,
        "has_data":     1 if has_data else 0,

        # 3. Timing
        "duration_s":   round(pipeline_duration_s, 3),
        "exec_ms":      sql_exec_ms,
        "llm_s":        llm_time_est,

        # 4. Question Profile
        "q_type":       question_type,
        "q_lvl":        complexity,
        "ext_kb":       1 if getattr(state, "external_knowledge", None) else 0,

        # 5. Database Profile
        "db_tables":    db_tables,
        "fk_density":   fk_density,
        "schema_cols":  schema_size,
        "tbl_used":     tables_used,
        "tbl_cov":      cov_ratio,
        "cache_hit":    cache_hit,

        # 6. SQL Generation
        "iters":        iter_count,
        "first_pass":   1 if iter_count <= 1 else 0,
        "retried":      1 if iter_count > 1 else 0,
        "critic_rej":   len(feedback_hist),
        "exec_errs":    len(exec_errors),
        "sql_approach": sql_approach,

        # 7. SQL Structure
        "sql_score":    sql_complexity,
        "joins":        sql_joins,
        "has_cte":      sql_cte,
        "has_wfn":      sql_window,
        "has_subq":     sql_subq,
        "has_agg":      sql_agg,
        "has_case":     sql_case,
        "sql_lines":    sql_lines,

        # 8. Failure
        "fail_stage":   failure_stage,
        "err_cat":      error_category,
        "err_msg":      last_err[:300],

        # 9. Cost
        "tok_in":       tok_in,
        "tok_out":      tok_out,
        "tok_total":    tok_total,
        "cost_usd":     cost_usd,
        "cost_per_row": cost_per_row,
    }

    db_name = state.db_name or "unknown"
    metrics_path = _metrics_path(db_name)

    with _write_lock:
        _ensure_header(metrics_path)
        existing = _load_existing(metrics_path)
        existing[state.instance_id] = row  # upsert by instance_id (matches "id" key)

        with open(metrics_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(existing.values())
