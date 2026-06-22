from agent.app.core.config import MEMORY_DIR
import asyncio
from agent.app.core.config import RESULTS_DIR
from agent.app.core.learning.lesson_rollback import LessonRollback
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import os
import re
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import lru_cache
from datetime import datetime
import contextlib

from agent.app.core.config import DAB_RESULTS_DIR, DEFAULT_USERNAME
from agent.app.core.dependencies import EXECUTION_POOL
from agent.app.utils.logger import logger
from sqlalchemy import cast, Date

router = APIRouter()

# ===========================================================================
# DAB (DataAgentBench) Endpoints ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â completely isolated from Spider2-Lite code
# ===========================================================================

from agent.app.core.config import DAB_REPO as _DAB_REPO

DAB_REPO_PATH_DEFAULT = str(_DAB_REPO)
DAB_RESULTS_BASE = DAB_RESULTS_DIR

from agent.app.utils.cache import (
    RedisBool,
    RedisInt,
    RedisSet,
    DAB_RUNNING_TASKS,
    DAB_EXECUTING_TASKS,
    DAB_CANCEL_FLAG,
    DAB_TOTAL_TASKS,
)
_dab_queries_cache = None


def _get_username_from_request(request: Request) -> str:
    """Extract sanitised username from X-Username header (injected by Go gateway from JWT).
    Falls back to DEFAULT_USERNAME for requests without auth or in local dev mode."""
    raw = request.headers.get("X-Username", "").strip()
    if not raw:
        raw = request.headers.get("X-User-Email", "").strip()
        # Derive local-part of email as username
        if "@" in raw:
            raw = raw.split("@")[0]
    safe = re.sub(r'[^a-z0-9_\-]', '', raw.lower()) if raw else ""
    return safe or DEFAULT_USERNAME


def _resolve_live_run_id(run_id: Optional[str], username: str) -> Optional[str]:
    """Resolve 'live' run_id to the active run ID if running, or the most recent run ID."""
    import agent.app.dab.dab_evaluator as de
    if run_id != "live":
        return run_id
    
    # If a run is actively processing, always use that active run ID
    if de.DAB_RUN_ID and de.DAB_RUN_ID != "live":
        return de.DAB_RUN_ID
        
    # Otherwise, fallback to the most recent run for this user
    from agent.app.core.config import get_user_dab_results_dir
    archive_base = get_user_dab_results_dir(username) / "_archive"
    archive_runs = []
    if archive_base.exists():
        for item in archive_base.iterdir():
            if item.is_dir() and item.name.startswith("run_"):
                archive_runs.append(item.name)
                
    legacy_archive_base = DAB_RESULTS_BASE / "_archive"
    if legacy_archive_base.exists():
        for item in legacy_archive_base.iterdir():
            if item.is_dir() and item.name.startswith("run_"):
                if item.name not in archive_runs:
                    archive_runs.append(item.name)
                    
    if archive_runs:
        archive_runs = sorted(archive_runs, reverse=True)
        return archive_runs[0]
        
    return "live"


def _get_dab_queries():
    """Lazy-load and cache all DAB queries from the repo."""
    global _dab_queries_cache
    if _dab_queries_cache is not None:
        return _dab_queries_cache
    try:
        from agent.app.dab.benchmark_loader import load_all_queries

        _dab_queries_cache = load_all_queries(DAB_REPO_PATH_DEFAULT)
    except Exception:
        _dab_queries_cache = []
    return _dab_queries_cache


def _dab_query_status(dataset: str, query_id: str, date: str = "all", run_id: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
    """Get the live status of a specific DAB query execution, aggregating across runs."""
    query_id = query_id.lower().replace("query", "")
    qkey = f"{dataset}_q{query_id}"

    is_executing = any(k == qkey or k.startswith(f"{qkey}_run") for k in DAB_EXECUTING_TASKS)
    if is_executing:
        return {"status": "running", "passed": None, "reason": "", "evaluated": False, "latency": 0}
    is_running = any(k == qkey or k.startswith(f"{qkey}_run") for k in DAB_RUNNING_TASKS)
    if is_running:
        return {"status": "pending", "passed": None, "reason": "", "evaluated": False, "latency": 0}

    runs_found = []
    any_passed = False
    best_result = None

    from agent.app.dab.dab_evaluator import load_all_eval_results
    for i, rv in enumerate(load_all_eval_results(dataset, query_id, date=date, run_id=run_id, username=username)):
        rv["run_num"] = i
        runs_found.append(rv)
        if rv.get("passed"):
            any_passed = True
            if not best_result or not best_result.get("passed"):
                best_result = rv

    if not runs_found:
        return {"status": "pending", "passed": None, "reason": "", "evaluated": False, "latency": 0}

    if best_result is None:
        best_result = runs_found[0]

    total_input = sum(rv.get("input_tokens", 0) or 0 for rv in runs_found)
    total_output = sum(rv.get("output_tokens", 0) or 0 for rv in runs_found)
    avg_latency = sum(rv.get("elapsed_s", 0) or 0 for rv in runs_found) / len(runs_found)

    run_0_passed = any(bool(rv.get("passed")) for rv in runs_found if rv.get("run_num") == 0)
    passing_runs = sum(1 for rv in runs_found if rv.get("passed"))
    total_runs = len(runs_found)
    runs_detail = [{"run_num": rv["run_num"], "passed": bool(rv.get("passed")), "reason": rv.get("reason", "")} for rv in runs_found]
    reason_str = best_result.get("reason", "") if best_result else ""

    return {
        "status": "passed" if any_passed else "failed",
        "passed": any_passed,
        "run_0_passed": run_0_passed,
        "passing_runs": passing_runs,
        "total_runs": total_runs,
        "runs": runs_detail,
        "reason": reason_str,
        "method": best_result.get("method", ""),
        "timestamp": best_result.get("timestamp", ""),
        "agent_answer": best_result.get("agent_answer_snippet", ""),
        "ground_truth": best_result.get("ground_truth", ""),
        "evaluated": True,
        "latency": round(avg_latency, 2),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "run_suffix": f"_run{best_result['run_num']}" if best_result.get("run_num", 0) > 0 else "",
    }


def get_dab_dataset_stats(dataset: str, db_clients: dict, db_description: str) -> tuple[int, int]:
    """Calculate schema token count and tables count for a DAB dataset."""
    tokens = len(db_description) // 4 if db_description else 0
    tables_count = 0
    
    # Try counting from db_clients files
    for client in db_clients.values():
        db_type = client.get("db_type", "").lower()
        db_path_str = client.get("db_path")
        if not db_path_str:
            continue
        db_path = Path(db_path_str)
        if not db_path.exists():
            continue
            
        if db_type == "sqlite":
            try:
                import sqlite3
                conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=1.0)
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
                tables_count += cursor.fetchone()[0]
                conn.close()
            except Exception:
                pass
        elif db_type == "duckdb":
            try:
                import duckdb
                conn = duckdb.connect(str(db_path), read_only=True)
                tables_count += conn.execute("SELECT count(*) FROM information_schema.tables;").fetchone()[0]
                conn.close()
            except Exception:
                pass
        elif db_path.suffix.lower() == ".sql":
            try:
                with open(db_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                tables_count += len(re.findall(r'create\s+table\s+(\w+|\"[^\"]+\"|\`[^\`]+\`)', content, re.IGNORECASE))
            except Exception:
                pass
                
    if tables_count > 0:
        return tokens, tables_count
        
    # Heuristics fallback: parse from description text
    if db_description:
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "a": 1, "single": 1
        }
        matches = re.findall(r'consists\s+of\s+(\w+|\d+)\s+table', db_description, re.IGNORECASE)
        for m in matches:
            m = m.lower()
            if m.isdigit():
                tables_count += int(m)
            elif m in word_to_num:
                tables_count += word_to_num[m]
                
        if tables_count == 0:
            tables_count = max(2, len(re.findall(r'table\b', db_description, re.IGNORECASE)) // 2)

    return tokens, max(1, tables_count)


@lru_cache(maxsize=128)
def cached_dab_dataset_stats(dataset: str, db_clients_json: str, db_description: str) -> tuple[int, int]:
    """LRU cache wrapper for get_dab_dataset_stats."""
    db_clients = json.loads(db_clients_json)
    return get_dab_dataset_stats(dataset, db_clients, db_description)

import time
def _get_ttl_hash(seconds=3):
    return round(time.time() / seconds)

@lru_cache(maxsize=128)
def _cached_dab_metrics(date: str, run_id: Optional[str], username: str, ttl_hash: int):
    """Compute DAB accuracy metrics with TTL caching, scoped per user."""
    try:
        from agent.app.dab.dab_evaluator import compute_accuracy

        queries = _get_dab_queries()
        metrics = compute_accuracy(queries, date=date, run_id=run_id, username=username)
        
        # Format and attach display fields
        evaluated        = metrics.get("evaluated", 0)
        total_run_slots  = metrics.get("total_run_slots", 0)
        total_time       = metrics.get("total_elapsed_time_s", 0)
        total_input_tok  = metrics.get("total_input_tokens", 0)
        total_output_tok = metrics.get("total_output_tokens", 0)
        total_tokens     = total_input_tok + total_output_tok

        # Cost estimate: claude-sonnet-4-x Bedrock pricing ($3/1M input, $15/1M output)
        cost = (total_input_tok * 3.0 / 1_000_000) + (total_output_tok * 15.0 / 1_000_000)

        metrics["passed"] = metrics.get("queries_passed_atk", 0)
        metrics["failed"] = evaluated - metrics["passed"]

        # Per-run-slot averages (each run is one independent agent invocation)
        metrics["avg_latency"] = (
            f"{total_time / total_run_slots:.1f}s" if total_run_slots > 0 else "0.0s"
        )
        metrics["avg_tokens_per_run"] = (
            f"{int(total_tokens / total_run_slots):,} tokens" if total_run_slots > 0 else "0 tokens"
        )
        metrics["avg_tokens_per_agent"] = metrics["avg_tokens_per_run"]  # alias kept for UI compat

        metrics["total_tokens"] = (
            f"{total_tokens / 1_000_000:.2f}M" if total_tokens >= 1_000_000
            else f"{total_tokens / 1_000:.1f}K" if total_tokens > 0
            else "0"
        )
        metrics["total_cost"] = f"${cost:.4f}"
        metrics["avg_cost_per_run"] = (
            f"${cost / total_run_slots:.4f}" if total_run_slots > 0 else "$0.0000"
        )
        metrics["avg_cost_per_query"] = metrics["avg_cost_per_run"]  # alias kept for UI compat
        
        return metrics
    except Exception as e:
        return {
            "error": str(e),
            "total_queries": 0,
            "evaluated": 0,
            "pending": 0,
            "total_run_slots": 0,
            "passing_run_slots": 0,
            "num_runs": 0,
            "queries_passed_atk": 0,
            "passed": 0,
            "failed": 0,
            "pass_at_1": 0.0,
            "pass_at_1_pct": "0.0%",
            "pass_at_k": 0.0,
            "pass_at_k_pct": "0.0%",
            "per_dataset": {},
            "avg_latency": "0.0s",
            "avg_tokens_per_agent": "0 tokens",
            "total_cost": "$0.0000",
            "avg_cost_per_query": "$0.0000",
        }


@router.get("/api/dab/databases")
def get_dab_databases(request: Request, date: str = "all", run_id: Optional[str] = None, force: bool = False):
    """Return DAB datasets formatted like Spider databases."""
    username = _get_username_from_request(request)
    run_id = _resolve_live_run_id(run_id, username)
    import agent.app.dab.dab_evaluator as de
    if force or de.DAB_RUN_ID:
        _cached_dab_metrics.cache_clear()
    metrics = _cached_dab_metrics(date, run_id, username, _get_ttl_hash(15))
    per_dataset = metrics.get("per_dataset", {})
    
    # Retrieve DB schema / tokens info from the cached queries list
    queries = _get_dab_queries()
    dataset_info = {}
    for q in queries:
        ds = q["dataset"]
        if ds not in dataset_info:
            dataset_info[ds] = {
                "db_clients": q.get("db_clients", {}),
                "db_description": q.get("db_description", "")
            }
            
    databases = []
    for db_name, stats in per_dataset.items():
        total = stats.get("total", 0)
        pending = stats.get("pending", 0)
        evaluated = stats.get("evaluated", 0)
        passed = stats.get("passed_atk", 0)
        failed = evaluated - passed
        
        info = dataset_info.get(db_name, {})
        db_clients = info.get("db_clients", {})
        db_description = info.get("db_description", "")
        
        # Serialize db_clients for caching key
        db_clients_json = json.dumps(db_clients, sort_keys=True)
        tokens, tables_count = cached_dab_dataset_stats(db_name, db_clients_json, db_description)
        
        databases.append({
            "name": db_name,
            "status": "completed" if pending == 0 and total > 0 else "pending",
            "results_count": passed,
            "error_count": failed,
            "empty_count": 0,
            "total_questions": total,
            "run_slots": stats.get("run_slots", 0),
            "passing_slots": stats.get("passing_slots", 0),
            "tokens": tokens,
            "tables_count": tables_count,
        })
    
    return sorted(databases, key=lambda x: x["name"])


_DAB_FILE_CACHE = {}


def _get_csv_rows_cached(csv_file: Path) -> int:
    try:
        mtime = csv_file.stat().st_mtime
        size = csv_file.stat().st_size
        cache_key = f"csv_{csv_file}"
        
        cached = _DAB_FILE_CACHE.get(cache_key)
        if cached and cached["mtime"] == mtime and cached["size"] == size:
            return cached["rows_count"]
            
        rows_count = 0
        with open(csv_file, "r", encoding="utf-8", errors="replace") as f:
            rows_count = sum(1 for _ in f) - 1
            if rows_count < 0:
                rows_count = 0
                
        _DAB_FILE_CACHE[cache_key] = {
            "mtime": mtime,
            "size": size,
            "rows_count": rows_count
        }
        return rows_count
    except Exception:
        return 0


def _get_md_corrections_cached(md_file: Path) -> int:
    try:
        mtime = md_file.stat().st_mtime
        size = md_file.stat().st_size
        cache_key = f"md_{md_file}"
        
        cached = _DAB_FILE_CACHE.get(cache_key)
        if cached and cached["mtime"] == mtime and cached["size"] == size:
            return cached["corrections"]
            
        log_txt = md_file.read_text(encoding="utf-8", errors="replace")
        corrections = len(re.findall(r'self-correction|retrying|healing|self-corrector', log_txt, re.IGNORECASE))
        
        _DAB_FILE_CACHE[cache_key] = {
            "mtime": mtime,
            "size": size,
            "corrections": corrections
        }
        return corrections
    except Exception:
        return 0


@router.get("/api/dab/queries/db/{dataset}")
def get_dab_queries_by_db(dataset: str, request: Request, date: str = "all", run_id: Optional[str] = None):
    """Return queries for a specific DAB dataset."""
    username = _get_username_from_request(request)
    run_id = _resolve_live_run_id(run_id, username)
    queries = _get_dab_queries()
    db_queries = [q for q in queries if q.get("dataset") == dataset]
    
    result = []
    for q in db_queries:
        status_info = _dab_query_status(q["dataset"], q["query_id"], date=date, run_id=run_id, username=username)
        dbtypes = list({cfg.get("db_type", "?") for cfg in q.get("db_clients", {}).values()})
        
        # Calculate tokens and cost
        input_t = status_info.get("input_tokens", 0) or 0
        output_t = status_info.get("output_tokens", 0) or 0
        total_tokens = input_t + output_t
        cost = (input_t * 0.15 / 1000000.0) + (output_t * 0.60 / 1000000.0)
        
        # Calculate rows count from CSV (cached)
        rows_count = 0
        from agent.app.core.config import get_user_dab_results_dir
        user_dab_dir = get_user_dab_results_dir(username)
        
        if run_id and run_id != "live" and run_id != "all":
            target_results_dir = user_dab_dir / "_archive" / run_id
            legacy_results_dir = DAB_RESULTS_BASE / "_archive" / run_id
        else:
            target_results_dir = user_dab_dir
            legacy_results_dir = DAB_RESULTS_BASE

        run_sfx = status_info.get("run_suffix", "")
        csv_file = target_results_dir / q["dataset"] / f"query{q['query_id']}{run_sfx}.csv"
        if not csv_file.exists():
            csv_file = legacy_results_dir / q["dataset"] / f"query{q['query_id']}{run_sfx}.csv"
        if csv_file.exists():
            rows_count = _get_csv_rows_cached(csv_file)
                
        # Corrections count from md log (cached)
        corrections = 0
        md_file = target_results_dir / q["dataset"] / f"query{q['query_id']}{run_sfx}.md"
        if not md_file.exists():
            md_file = legacy_results_dir / q["dataset"] / f"query{q['query_id']}{run_sfx}.md"
        if md_file.exists():
            corrections = _get_md_corrections_cached(md_file)

        result.append(
            {
                "id": f"{q['dataset']}_q{q['query_id']}",
                "question": q["question"],
                "status": status_info["status"],
                "gold_status": "gold_pass" if status_info.get("passed") is True else "gold_fail" if status_info.get("passed") is False else None,
                "complexity": "relational_complexity" if q["needs_docker"] else "linear_logic",
                "complexity_type": "Docker" if q["needs_docker"] else "Standard",
                "complexity_score": 0.75 if q["needs_docker"] else 0.2,
                "latency": status_info.get("latency", 0) or 0,
                "corrections": corrections,
                "critic_rounds": 0,
                "rows": rows_count,
                "cost": cost,
                "total_tokens": total_tokens,
                "db_id": q["dataset"],
                "evidence": q.get("external_knowledge", ""),
                "spider_query": "",
                "sql": "",
                "error": status_info.get("reason", ""),
                "passed": status_info.get("passed"),
                "dbtypes": dbtypes,
            }
        )
    return result

@router.get("/api/dab/queries")
def get_dab_queries(request: Request, date: str = "all", run_id: Optional[str] = None):
    """List all 54 DAB queries with their current status."""
    username = _get_username_from_request(request)
    run_id = _resolve_live_run_id(run_id, username)
    queries = _get_dab_queries()
    result = []
    for q in queries:
        status_info = _dab_query_status(q["dataset"], q["query_id"], date=date, run_id=run_id, username=username)
        dbtypes = list({cfg.get("db_type", "?") for cfg in q["db_clients"].values()})
        result.append(
            {
                "instance_id": q["instance_id"],
                "dataset": q["dataset"],
                "query_id": q["query_id"],
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "db_types": dbtypes,
                "needs_docker": q["needs_docker"],
                "has_hint": q["has_hint"],
                **status_info,
            }
        )
    return result


@router.get("/api/dab/metrics")
def get_dab_metrics(request: Request, date: str = "all", run_id: Optional[str] = None, force: bool = False):
    """Get overall DAB accuracy metrics."""
    username = _get_username_from_request(request)
    run_id = _resolve_live_run_id(run_id, username)
    import agent.app.dab.dab_evaluator as de
    if force or de.DAB_RUN_ID:
        _cached_dab_metrics.cache_clear()
    return _cached_dab_metrics(date, run_id, username, _get_ttl_hash(5))


@router.get("/api/dab/submissions")
def get_dab_submissions():
    """Get the parsed benchmark submission evaluation results."""
    summary_path = Path(__file__).resolve().parent / "dab" / "submissions_summary.json"
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to load submissions summary: {e}"}
    return []


def _get_query_difficulty(q: dict) -> str:
    question = q.get("question", "").lower()
    needs_docker = q.get("needs_docker", False)
    
    if needs_docker:
        return "tough"
    
    keywords_tough = ["decade", "highest average", "distinct", "having", "ratio", "percentage", "failed", "correlated", "subquery", "subqueries"]
    keywords_medium = ["average", "count", "maximum", "minimum", "total", "join", "filter", "group", "sort", "order by"]
    
    if any(k in question for k in keywords_tough) or len(question) > 180:
        return "tough"
    elif any(k in question for k in keywords_medium) or len(question) > 100:
        return "medium"
    else:
        return "easy"


def _classify_error(reason: str, content: str) -> str:
    reason_lower = (reason or "").lower()
    content_lower = (content or "").lower()
    
    # 1. LLM Throttling/Rate Limit
    if any(w in reason_lower or w in content_lower for w in ["rate limit", "throttled", "request limit", "429", "circuit breaker", "circuitbreaker"]):
        return "llm_rate_limit"
    # 2. LLM Timeout
    if any(w in reason_lower or w in content_lower for w in ["timeout", "timed out", "readtimeout", "connection timeout"]):
        if "exceeded 30 seconds" in reason_lower:
            return "execution_timeout"
        return "llm_timeout"
    # 3. LLM Generation/Parsing
    if any(w in reason_lower or w in content_lower for w in ["jsondecodeerror", "failed to parse", "invalid json", "json parse"]):
        return "llm_generation"
    # 4. DB Connection/Access
    if any(w in reason_lower or w in content_lower for w in ["connectionrefused", "database is locked", "operationalerror", "connection not established", "mongo", "mongodb"]):
        return "db_connection"
    # 5. SQL Syntax/Parsing
    if any(w in reason_lower or w in content_lower for w in ["syntax error", "parseerror", "invalid sql", "sqlglot"]):
        return "sql_syntax"
    # 6. Execution Timeout
    if "exceeded 30 seconds" in reason_lower or "killed" in reason_lower:
        return "execution_timeout"
    # 7. Schema/Pruner Truncation
    if any(w in reason_lower or w in content_lower for w in ["prun", "token limit", "context length"]):
        return "schema_pruning"
    
    return "other_errors"


@router.get("/api/dab/agent_analytics")
def get_dab_agent_analytics(request: Request, date: str = "all", run_id: Optional[str] = None):
    """Get DAB Agent Analytics including tool scores, difficulty stats, error categories, and plots data."""
    username = _get_username_from_request(request)
    run_id = _resolve_live_run_id(run_id, username)
    from agent.app.db.database import SessionLocal
    from agent.app.db.models import Evaluation
    from agent.app.core.config import get_user_dab_results_dir
    import re

    db = SessionLocal()
    try:
        # 1. Fetch matching evaluations
        query = db.query(Evaluation).filter(Evaluation.username == username)
        if run_id is not None:
            if run_id == "all":
                pass
            elif run_id == "live":
                query = query.filter((Evaluation.run_id == "live") | (Evaluation.run_id == None))
            else:
                query = query.filter(Evaluation.run_id == run_id)
        elif date != "all":
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=1)
            query = query.filter(
                Evaluation.timestamp >= start_dt,
                Evaluation.timestamp < end_dt
            )
        
        evals = query.all()
        
        # Load benchmark queries to map question text and properties
        queries = _get_dab_queries()
        q_map = {(q["dataset"].lower(), str(q["query_id"])): q for q in queries}
        
        # User results dir
        user_dab_dir = get_user_dab_results_dir(username)
        if run_id and run_id != "live" and run_id != "all":
            target_results_dir = user_dab_dir / "_archive" / run_id
            legacy_results_dir = DAB_RESULTS_DIR / "_archive" / run_id
        else:
            target_results_dir = user_dab_dir
            legacy_results_dir = DAB_RESULTS_DIR
            
        queries_analytics = []
        
        # Aggregate statistics
        diff_stats = {
            "easy": {"total": 0, "passed": 0, "failed": 0},
            "medium": {"total": 0, "passed": 0, "failed": 0},
            "tough": {"total": 0, "passed": 0, "failed": 0}
        }
        
        error_counts = {
            "llm_rate_limit": 0,
            "llm_timeout": 0,
            "llm_generation": 0,
            "db_connection": 0,
            "sql_syntax": 0,
            "execution_timeout": 0,
            "schema_pruning": 0,
            "other_errors": 0,
        }
        
        agent_scores_sum = {
            "schema_linker": 0,
            "sql_generator": 0,
            "critic": 0,
            "self_corrector": 0,
            "data_iq": 0,
        }
        agent_counts = {
            "schema_linker": 0,
            "sql_generator": 0,
            "critic": 0,
            "self_corrector": 0,
            "data_iq": 0,
        }
        
        for ev in evals:
            dataset_lower = ev.dataset.lower()
            q_info = q_map.get((dataset_lower, str(ev.query_id)))
            if not q_info:
                continue
                
            difficulty = _get_query_difficulty(q_info)
            passed = bool(ev.passed)
            
            # Update difficulty totals
            diff_stats[difficulty]["total"] += 1
            if passed:
                diff_stats[difficulty]["passed"] += 1
            else:
                diff_stats[difficulty]["failed"] += 1
                
            # Log parsing for agent scores
            run_suffix = ev.run_suffix or ""
            md_file = target_results_dir / ev.dataset / f"query{ev.query_id}{run_suffix}.md"
            if not md_file.exists():
                md_file = legacy_results_dir / ev.dataset / f"query{ev.query_id}{run_suffix}.md"
                
            content = ""
            if md_file.exists():
                try:
                    content = md_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            
            from collections import defaultdict
            agent_calls = defaultdict(int)
            agent_errors = defaultdict(int)

            if content:
                # Find all agent log lines like "04:06:42 | DATA_IQ      | INFO     | Evaluating result quality"
                for match in re.finditer(r"\|\s*([A-Z_]+)\s*\|\s*(INFO|WARNING|ERROR)\s*\|", content):
                    agent = match.group(1).strip()
                    level = match.group(2).strip()
                    # Skip common non-agents
                    if agent in ["ROOT", "MAIN", "DAB_EVALUATOR", "AGENT", "RESULT"]:
                        continue
                    agent_calls[agent] += 1
                    if level in ["ERROR", "WARNING"]:
                        agent_errors[agent] += 1
            
            # Forensic Error Analytics: classify failed evaluations
            if not passed:
                err_category = _classify_error(ev.reason, content)
                error_counts[err_category] += 1

            # Premium, highly granular agent performance rating logic
            query_agent_scores = {
                "schema_linker": 100,
                "sql_generator": 100,
                "critic": 100,
                "self_corrector": 100,
                "data_iq": 100,
            }
            
            reason_lower = (ev.reason or "").lower()
            content_lower = content.lower() if content else ""
            
            # 1. Schema Linker
            schema_linker_errs = agent_errors.get("SCHEMA_LINKER", 0)
            schema_linker_calls = agent_calls.get("SCHEMA_LINKER", 0)
            if schema_linker_calls > 0 or "schema_pruner" in content_lower:
                score = 100 - (20 * schema_linker_errs)
                if "prun" in reason_lower:
                    score -= 30
                if not passed and "no such column" in reason_lower:
                    score -= 15
                query_agent_scores["schema_linker"] = max(10, min(100, score))
            elif not passed:
                query_agent_scores["schema_linker"] = 80
                
            # 2. SQL Generator
            sql_gen_errs = agent_errors.get("SQL_GENERATOR", 0)
            sql_gen_calls = agent_calls.get("SQL_GENERATOR", 0)
            if sql_gen_calls > 0:
                score = 100 - (25 * sql_gen_errs)
                if "syntax error" in reason_lower or "parseerror" in reason_lower:
                    score -= 35
                if not passed:
                    score -= 15
                query_agent_scores["sql_generator"] = max(10, min(100, score))
            elif not passed:
                query_agent_scores["sql_generator"] = 80

            # 3. Critic
            critic_errs = agent_errors.get("CRITIC", 0)
            critic_calls = agent_calls.get("CRITIC", 0)
            if critic_calls > 0:
                score = 100 - (20 * critic_errs)
                if not passed:
                    score -= 25
                query_agent_scores["critic"] = max(10, min(100, score))
            elif not passed:
                query_agent_scores["critic"] = 90

            # 4. Self Corrector
            self_corrector_calls = agent_calls.get("SELF_CORRECTOR", 0)
            if self_corrector_calls > 0:
                if passed:
                    score = 100
                else:
                    score = 50 - (10 * agent_errors.get("SELF_CORRECTOR", 0))
                query_agent_scores["self_corrector"] = max(10, min(100, score))
            else:
                query_agent_scores["self_corrector"] = 100

            # 5. Data IQ
            data_iq_errs = agent_errors.get("DATA_IQ", 0)
            data_iq_calls = agent_calls.get("DATA_IQ", 0)
            if data_iq_calls > 0 or "classify" in content_lower:
                score = 100 - (15 * data_iq_errs)
                if "rate limit" in content_lower or "throttled" in content_lower:
                    score -= 20
                if not passed and "classify" in reason_lower:
                    score -= 25
                query_agent_scores["data_iq"] = max(10, min(100, score))
            elif not passed:
                query_agent_scores["data_iq"] = 85

            for agent_key, score in query_agent_scores.items():
                agent_scores_sum[agent_key] += score
                agent_counts[agent_key] += 1

            queries_analytics.append({
                "id": ev.instance_id + (f"_run{ev.run_suffix}" if ev.run_suffix else ""),
                "dataset": ev.dataset,
                "query_id": ev.query_id,
                "question": q_info["question"],
                "passed": passed,
                "difficulty": difficulty,
                "scores": query_agent_scores,  # Lowercase keys expected by frontend
                "details": {
                    "agents_active": len(agent_calls),
                    "total_errors": sum(agent_errors.values())
                }
            })
            
        # Calculate final averages
        avg_scores = {}
        for agent_key, total in agent_scores_sum.items():
            count = agent_counts[agent_key]
            avg_scores[agent_key] = round(total / count, 1) if count > 0 else 100.0
            
        # Format difficulty stats for response
        formatted_diff = {}
        for key, stats in diff_stats.items():
            total = stats["total"]
            failed = stats["failed"]
            pct_failed = round((failed / total) * 100, 1) if total > 0 else 0.0
            formatted_diff[key] = {
                "total": total,
                "passed": stats["passed"],
                "failed": failed,
                "pct_failed": pct_failed
            }
            
        total_failed = sum(1 for q in queries_analytics if not q["passed"])
        return {
            "avg_scores": avg_scores,
            "difficulty_metrics": formatted_diff,
            "error_metrics": error_counts,
            "total_failed": total_failed,
            "queries": queries_analytics,
            "total_evaluated": len(queries_analytics)
        }
        
    except Exception as e:
        logger.error(f"Failed to compile agent analytics: {e}")
        return {
            "error": str(e),
            "avg_scores": {
                "schema_linker": 100,
                "sql_generator": 100,
                "critic": 100,
                "self_corrector": 100,
                "data_iq": 100
            },
            "difficulty_metrics": {
                "easy": {"total": 0, "passed": 0, "failed": 0, "pct_failed": 0.0},
                "medium": {"total": 0, "passed": 0, "failed": 0, "pct_failed": 0.0},
                "tough": {"total": 0, "passed": 0, "failed": 0, "pct_failed": 0.0}
            },
            "queries": [],
            "total_evaluated": 0
        }
    finally:
        db.close()


@router.get("/api/dab/smartness_timeseries")
def get_smartness_timeseries():
    """Return per-run smartness scores and per-batch accuracy for time-series charts.

    Smartness scores come from PipelineRun (internal orchestrator metric).
    Accuracy comes from the Evaluation table (ground-truth benchmark comparison).
    No hallucinated values — every number is derived from actual stored data.
    """
    import re as _re
    from agent.app.db.models import PipelineRun, Evaluation
    from agent.app.db.database import SessionLocal

    db = SessionLocal()
    try:
        # ── Smartness time-series (PipelineRun) ──────────────────────────────
        runs = (
            db.query(PipelineRun)
            .filter(PipelineRun.smartness_score.isnot(None))
            .order_by(PipelineRun.timestamp.asc())
            .all()
        )

        smartness_rows: list[dict] = []
        all_scores: list[float] = []

        for i, run in enumerate(runs):
            all_scores.append(run.smartness_score)
            n = len(all_scores)
            weights = list(range(1, n + 1))
            cumulative_avg = round(
                sum(s * w for s, w in zip(all_scores, weights)) / sum(weights), 2
            )
            date_str = run.timestamp.strftime("%Y-%m-%d") if run.timestamp else ""
            smartness_rows.append({
                "run_num": i + 1,
                "label": f"Run {i + 1}",
                "date": date_str,
                "instance_id": run.instance_id,
                "smartness_score": round(run.smartness_score, 1),
                "cumulative_avg": cumulative_avg,
                "grade": run.smartness_grade or "",
                "final_verdict": run.final_verdict or "",
                "attempts": run.total_attempts or 1,
            })

        # ── Accuracy time-series (Evaluation — ground truth) ─────────────────
        # Group Evaluation rows into batches using a 30-min gap heuristic,
        # then produce one accuracy point per batch.
        all_evals = (
            db.query(Evaluation)
            .filter(Evaluation.timestamp.isnot(None))
            .order_by(Evaluation.timestamp.asc())
            .all()
        )

        accuracy_rows: list[dict] = []
        latest_batch: dict = {}

        if all_evals:
            # Split into time-batches (gap > 30 min between consecutive rows = new batch)
            batches: list[list] = [[all_evals[0]]]
            for ev in all_evals[1:]:
                gap_min = (ev.timestamp - batches[-1][-1].timestamp).total_seconds() / 60
                if gap_min > 30:
                    batches.append([])
                batches[-1].append(ev)

            for b_idx, batch in enumerate(batches):
                total = len(batch)
                passed = sum(1 for e in batch if e.passed)
                acc = round(passed / total * 100, 1) if total else 0.0
                date_str = batch[0].timestamp.strftime("%Y-%m-%d") if batch[0].timestamp else ""
                label = f"Batch {b_idx + 1} ({date_str})"

                # Per-dataset breakdown for this batch
                by_ds: dict[str, dict] = {}
                for e in batch:
                    ds = e.dataset or "unknown"
                    if ds not in by_ds:
                        by_ds[ds] = {"passed": 0, "total": 0}
                    by_ds[ds]["total"] += 1
                    if e.passed:
                        by_ds[ds]["passed"] += 1

                row = {
                    "batch_num": b_idx + 1,
                    "label": label,
                    "date": date_str,
                    "total": total,
                    "passed": passed,
                    "failed": total - passed,
                    "accuracy": acc,
                    "by_dataset": {
                        ds: {
                            "passed": v["passed"],
                            "total": v["total"],
                            "accuracy": round(v["passed"] / v["total"] * 100, 1),
                        }
                        for ds, v in sorted(by_ds.items())
                    },
                }
                accuracy_rows.append(row)

            # Latest batch summary (most recent batch, sorted newest first)
            lb = accuracy_rows[-1] if accuracy_rows else {}
            latest_batch = {
                "batch_num": lb.get("batch_num"),
                "date": lb.get("date"),
                "total": lb.get("total", 0),
                "passed": lb.get("passed", 0),
                "failed": lb.get("failed", 0),
                "accuracy": lb.get("accuracy", 0.0),
                "by_dataset": lb.get("by_dataset", {}),
            }

        return {
            "smartness": smartness_rows,
            "accuracy": accuracy_rows,
            "latest_batch": latest_batch,
            "total_runs": len(runs),
            "total_batches": len(accuracy_rows),
        }

    except Exception as e:
        logger.error(f"Failed to build smartness timeseries: {e}")
        return {
            "smartness": [], "accuracy": [], "latest_batch": {},
            "total_runs": 0, "total_batches": 0, "error": str(e),
        }
    finally:
        db.close()


@router.get("/api/dab/results/{dataset}/{query_id}")
def get_dab_result(dataset: str, query_id: str, request: Request, date: str = "all", run_id: Optional[str] = None):
    """Get full result details for a specific DAB query."""
    username = _get_username_from_request(request)
    run_id = _resolve_live_run_id(run_id, username)
    query_id = query_id.lower().replace("query", "")
    from agent.app.dab.dab_evaluator import load_eval_result
    from agent.app.utils.archive import get_target_dirs_for_date
    from agent.app.core.config import get_user_dab_results_dir

    username = _get_username_from_request(request)
    user_dab_dir = get_user_dab_results_dir(username)

    # Find the best run suffix (first passing run, or run 0)
    run_suffix = ""
    for r in range(10):
        sfx = "" if r == 0 else f"_run{r}"
        rv = load_eval_result(dataset, query_id, run_suffix=sfx, date=date, run_id=run_id, username=username)
        if rv is not None:
            if rv.get("passed"):
                run_suffix = sfx
                break

    if run_id and run_id != "live" and run_id != "all":
        target_dirs = [user_dab_dir / "_archive" / run_id]
    else:
        target_dirs = get_target_dirs_for_date(user_dab_dir, date)
    
    md_file = None
    sql_file = None
    csv_file = None
    answer_file = None
    
    # Check user-scoped target directories first
    for t_dir in target_dirs:
        if (t_dir / dataset / f"query{query_id}{run_suffix}.md").exists():
            result_dir = t_dir / dataset
            md_file = result_dir / f"query{query_id}{run_suffix}.md"
            sql_file = result_dir / f"query{query_id}{run_suffix}.sql"
            csv_file = result_dir / f"query{query_id}{run_suffix}.csv"
            answer_file = result_dir / f"query{query_id}{run_suffix}_answer.txt"
            break
            
    # Check legacy target directories fallback
    if md_file is None:
        if run_id and run_id != "live" and run_id != "all":
            legacy_target_dirs = [DAB_RESULTS_BASE / "_archive" / run_id]
        else:
            legacy_target_dirs = get_target_dirs_for_date(DAB_RESULTS_BASE, date)
            
        for t_dir in legacy_target_dirs:
            if (t_dir / dataset / f"query{query_id}{run_suffix}.md").exists():
                result_dir = t_dir / dataset
                md_file = result_dir / f"query{query_id}{run_suffix}.md"
                sql_file = result_dir / f"query{query_id}{run_suffix}.sql"
                csv_file = result_dir / f"query{query_id}{run_suffix}.csv"
                answer_file = result_dir / f"query{query_id}{run_suffix}_answer.txt"
                break

    # If not found in target_dirs (e.g. active run), check active results folder
    if md_file is None:
        result_dir = user_dab_dir / dataset
        md_file = result_dir / f"query{query_id}{run_suffix}.md"
        sql_file = result_dir / f"query{query_id}{run_suffix}.sql"
        csv_file = result_dir / f"query{query_id}{run_suffix}.csv"
        answer_file = result_dir / f"query{query_id}{run_suffix}_answer.txt"
        
        # Check active legacy results folder fallback
        if not md_file.exists():
            legacy_result_dir = DAB_RESULTS_BASE / dataset
            if (legacy_result_dir / f"query{query_id}{run_suffix}.md").exists():
                result_dir = legacy_result_dir
                md_file = result_dir / f"query{query_id}{run_suffix}.md"
                sql_file = result_dir / f"query{query_id}{run_suffix}.sql"
                csv_file = result_dir / f"query{query_id}{run_suffix}.csv"
                answer_file = result_dir / f"query{query_id}{run_suffix}_answer.txt"

    log_content = ""
    sql_content = ""
    csv_headers = []
    csv_data = []
    agent_answer = ""

    if md_file.exists():
        with contextlib.suppress(Exception):
            log_content = md_file.read_text(encoding="utf-8", errors="replace")[:50000]

    if sql_file.exists():
        with contextlib.suppress(Exception):
            sql_content = sql_file.read_text(encoding="utf-8").strip()

    if answer_file.exists():
        with contextlib.suppress(Exception):
            agent_answer = answer_file.read_text(encoding="utf-8").strip()

    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            csv_headers = df.columns.tolist()
            raw = df.head(50).to_dict(orient="records")
            clean = []
            for row in raw:  # type: ignore
                cr = {}
                for k, v in row.items():
                    if (isinstance(v, (float, np.floating)) and (
                        np.isnan(v) or np.isinf(v)
                    )) or pd.isna(v):
                        cr[k] = None
                    else:
                        cr[k] = v
                clean.append(cr)
            csv_data = clean
        except Exception:
            pass

    eval_result = load_eval_result(dataset, query_id, run_suffix=run_suffix, date=date, run_id=run_id, username=username)
    status_info = _dab_query_status(dataset, query_id, date=date, run_id=run_id, username=username)

    return {
        **status_info,
        "dataset": dataset,
        "query_id": query_id,
        "log_content": log_content,
        "sql_content": sql_content,
        "csv_headers": csv_headers,
        "csv_data": csv_data,
        "agent_answer": agent_answer,
        "eval_detail": eval_result,
    }


class DabRunSinglePayload(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = None
    run_id: Optional[str] = None


@router.post("/api/dab/run/{dataset}/{query_id}")
def run_dab_single(dataset: str, query_id: str, request: Request, payload: DabRunSinglePayload = DabRunSinglePayload()):
    """Run a single DAB query through the agent pipeline."""
    query_id = query_id.lower().replace("query", "")
    from agent.app.dab.dab_orchestrator import run_dab_query
    import agent.app.dab.dab_evaluator as de

    username = _get_username_from_request(request)

    qkey = f"{dataset}_q{query_id}"
    if qkey in DAB_RUNNING_TASKS:
        return {"message": f"Query {qkey} is already running."}

    queries = _get_dab_queries()
    target = next(
        (
            q
            for q in queries
            if q["dataset"] == dataset and q["query_id"] == str(query_id)
        ),
        None,
    )
    if not target:
        return {"error": f"Query {qkey} not found in DAB index."}

    DAB_RUNNING_TASKS.add(qkey)

    def _execute():
        from agent.app.services.task_manager import TaskManager
        task_id = TaskManager.start_task('dab_query', qkey)
        
        # Set username and ID in dab_evaluator module
        de.DAB_RUN_USERNAME = username
        de.DAB_RUN_DATE = None
        de.DAB_RUN_ID = payload.run_id or "live"
        
        try:
            run_dab_query(target, model=payload.model, temperature=payload.temperature)
            TaskManager.complete_task(task_id, success=True)
        except Exception as e:
            TaskManager.complete_task(task_id, success=False, error_message=str(e))
            raise
        finally:
            DAB_RUNNING_TASKS.discard(qkey)
            # Invalidate metrics cache
            global _dab_queries_cache
            _dab_queries_cache = None
            _cached_dab_metrics.cache_clear()

    EXECUTION_POOL.submit(_execute)
    return {"message": f"Started DAB query {qkey}"}


@router.get("/api/dab/livelog/{dataset}/{query_id}")
def get_dab_live_log(dataset: str, query_id: str, request: Request):
    """
    Tail the live log file for a running DAB query.
    Returns parsed milestone steps from the log even while it's being written.
    """
    query_id = query_id.lower().replace("query", "")
    import re as _re
    from agent.app.core.config import get_user_dab_results_dir

    username = _get_username_from_request(request)
    user_dab_dir = get_user_dab_results_dir(username)

    qkey = f"{dataset}_q{query_id}"
    is_running = qkey in DAB_RUNNING_TASKS

    # Try user-scoped directories first
    import agent.app.dab.dab_evaluator as de
    run_id = de.DAB_RUN_ID
    md_file = None

    if run_id and run_id != "live":
        archive_dir = user_dab_dir / "_archive" / run_id
        for p in (
            archive_dir / dataset.lower() / f"query{query_id}.md",
            archive_dir / dataset.upper() / f"query{query_id}.md",
            archive_dir / dataset / f"query{query_id}.md",
        ):
            if p.exists():
                md_file = p
                break

    if md_file is None:
        md_file = user_dab_dir / dataset.lower() / f"query{query_id}.md"
        if not md_file.exists():
            md_file = user_dab_dir / dataset.upper() / f"query{query_id}.md"
        if not md_file.exists():
            md_file = user_dab_dir / dataset / f"query{query_id}.md"
        
    # Legacy / shared directories fallback
    if not md_file.exists():
        md_file = DAB_RESULTS_DIR / dataset.lower() / f"query{query_id}.md"
    if not md_file.exists():
        md_file = DAB_RESULTS_DIR / dataset.upper() / f"query{query_id}.md"
    if not md_file.exists():
        md_file = DAB_RESULTS_DIR / dataset / f"query{query_id}.md"
    if not md_file.exists():
        md_file = RESULTS_DIR / dataset.upper() / f"query{query_id}.md"
    if not md_file.exists():
        md_file = RESULTS_DIR / dataset / f"query{query_id}.md"

    if not md_file.exists():
        return {
            "is_running": is_running,
            "log_available": False,
            "live_steps": [],
            "current_phase": "Initializing Agent Orchestrator..." if is_running else "Pending",
        }

    try:
        with open(md_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return {
            "is_running": is_running,
            "log_available": False,
            "live_steps": [],
            "current_phase": "Reading agent logs...",
        }

    live_steps = []
    current_phase = "Initializing Agent Orchestrator..."

    # Always add the start step
    live_steps.append({"time": "00:01", "type": "start", "text": "Initializing autonomous pipeline container..."})

    # 1. Schema Linker / Database Grounding
    if _re.search(r"SchemaLinker|SCHEMA_LINKER|schema link|schema_linking", content, _re.IGNORECASE):
        current_phase = "Surgical Schema Pruning & Column Linker"
        live_steps.append({"time": "00:02", "type": "step", "text": "SchemaLinker: Pruning full schema to surgical candidate subset."})

    # 2. Context Pruner
    if _re.search(r"TablePruner|ColumnPruner|PRUNER|context prun", content, _re.IGNORECASE):
        current_phase = "Context Pruning & Token Budget"
        live_steps.append({"time": "00:03", "type": "step", "text": "ContextPruner: Eliminating unrelated schema structures."})

    # 3. Strategy Router
    if _re.search(r"feasibility_and_strategy|StrategyRouter|Router|Planner|dialect planner", content, _re.IGNORECASE):
        current_phase = "Strategy Router & Dialect Planner"
        live_steps.append({"time": "00:04", "type": "step", "text": "StrategyRouter: Evaluating dialect requirements and execution strategy."})

    # 4. SQL Synthesis
    if _re.search(r"SQLGenerator|SQL_GENERATOR|Generating SQL|SQL synthesis|profiling_and_generation", content, _re.IGNORECASE):
        current_phase = "Adaptive FQN SQL Generation"
        live_steps.append({"time": "00:05", "type": "step", "text": "SQLGenerator: Assembling deterministic joins and clauses."})

    # 5. Self Correction Loops
    corrections = len(_re.findall(r"Executing Self-Correction Module|Self-Correction attempt", content, _re.IGNORECASE))
    for i in range(corrections):
        live_steps.append({"time": f"00:0{6+i}", "type": "warn", "text": f"Self-Corrector: Automated SQL repair loop #{i+1} triggered."})
    if corrections > 0:
        current_phase = "Closed-Loop Execution Corrector"

    # 6. Result Auditor / Validator
    if _re.search(r"ResultValidator|DATA_IQ|Validator|Auditor|execution_and_audit", content, _re.IGNORECASE):
        current_phase = "Data IQ Execution Auditor"
        live_steps.append({"time": "00:08", "type": "step", "text": "Data IQ Auditor: Probing result grain, NULL density, and unit scale."})

    # 7. Final Outcomes (Success or Failure)
    if _re.search(r"SUCCESS|Final SQL|Query executed", content, _re.IGNORECASE):
        current_phase = "Pipeline Complete"
        live_steps.append({"time": "00:09", "type": "success", "text": "Pipeline complete. Query executed and results validated."})
    elif _re.search(r"ERROR|Traceback|failed", content, _re.IGNORECASE):
        current_phase = "Error Detected"
        live_steps.append({"time": "00:09", "type": "error", "text": "Error detected in pipeline. Check LOG tab for details."})

    # Deduplicate steps preserving order
    seen = set()
    clean = []
    for s in live_steps:
        if s["text"] not in seen:
            seen.add(s["text"])
            clean.append(s)

    return {
        "is_running": is_running,
        "log_available": True,
        "live_steps": clean,
        "current_phase": current_phase,
    }


@router.get("/api/dab/stream/{dataset}/{query_id}")
async def stream_dab_live_log(dataset: str, query_id: str, request: Request):
    """
    SSE endpoint ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â pushes log progress to the browser as events happen.
    Replaces client-side polling (was 1.5 s interval, now sub-100 ms latency).
    The browser uses EventSource; each message is a JSON-serialised step list.
    A final 'event: done' frame signals completion so the client can close.
    """
    import re as _re

    username = _get_username_from_request(request)
    qkey = f"{dataset}_q{query_id}"
    from agent.app.core.config import get_user_dab_results_dir
    user_dab_dir = get_user_dab_results_dir(username)

    import agent.app.dab.dab_evaluator as de
    run_id = de.DAB_RUN_ID

    def _resolve_md() -> Path | None:
        if run_id and run_id != "live":
            archive_dir = user_dab_dir / "_archive" / run_id
            for p in (
                archive_dir / dataset.lower() / f"query{query_id}.md",
                archive_dir / dataset.upper() / f"query{query_id}.md",
                archive_dir / dataset / f"query{query_id}.md",
            ):
                if p.exists():
                    return p
        for p in (
            user_dab_dir / dataset.lower() / f"query{query_id}.md",
            user_dab_dir / dataset.upper() / f"query{query_id}.md",
            user_dab_dir / dataset / f"query{query_id}.md",
            DAB_RESULTS_DIR / dataset.lower() / f"query{query_id}.md",
            DAB_RESULTS_DIR / dataset.upper() / f"query{query_id}.md",
            DAB_RESULTS_DIR / dataset / f"query{query_id}.md",
        ):
            if p.exists():
                return p
        return None

    def _parse_steps(content: str) -> dict:
        steps = [{"time": "00:01", "type": "start", "text": "Initializing autonomous pipeline container..."}]
        phase = "Initializing Agent Orchestrator..."
        if _re.search(r"SchemaLinker|schema_linking", content, _re.IGNORECASE):
            phase = "Surgical Schema Pruning"
            steps.append({"time": "00:02", "type": "step", "text": "SchemaLinker: Pruning schema to surgical candidate subset."})
        if _re.search(r"TablePruner|ColumnPruner|context prun", content, _re.IGNORECASE):
            phase = "Context Pruning"
            steps.append({"time": "00:03", "type": "step", "text": "ContextPruner: Eliminating unrelated schema structures."})
        if _re.search(r"StrategyRouter|feasibility_and_strategy", content, _re.IGNORECASE):
            phase = "Strategy Router"
            steps.append({"time": "00:04", "type": "step", "text": "StrategyRouter: Evaluating dialect and execution strategy."})
        if _re.search(r"SQLGenerator|SQL synthesis|profiling_and_generation", content, _re.IGNORECASE):
            phase = "SQL Generation"
            steps.append({"time": "00:05", "type": "step", "text": "SQLGenerator: Assembling deterministic joins and clauses."})
        corrections = len(_re.findall(r"Self-Correction attempt", content, _re.IGNORECASE))
        for i in range(corrections):
            steps.append({"time": f"00:0{6+i}", "type": "warn", "text": f"Self-Corrector: Repair loop #{i + 1}."})
        if corrections:
            phase = "Self-Correction Loop"
        if _re.search(r"ResultValidator|execution_and_audit", content, _re.IGNORECASE):
            phase = "Execution Auditor"
            steps.append({"time": "00:08", "type": "step", "text": "Data IQ Auditor: Probing result grain and NULL density."})
        if _re.search(r"SUCCESS|Final SQL", content, _re.IGNORECASE):
            phase = "Pipeline Complete"
            steps.append({"time": "00:09", "type": "success", "text": "Pipeline complete. Results validated."})
        elif _re.search(r"\bERROR\b|Traceback", content, _re.IGNORECASE):
            phase = "Error Detected"
            steps.append({"time": "00:09", "type": "error", "text": "Error detected. Check LOG tab for details."})
        seen: set[str] = set()
        clean = [s for s in steps if s["text"] not in seen and not seen.add(s["text"])]  # type: ignore[func-returns-value]
        return {"live_steps": clean, "current_phase": phase}

    async def _event_stream():
        last_size = -1
        last_steps_count = -1

        while True:
            # Honour client disconnect — avoids leaking coroutines
            if await request.is_disconnected():
                break

            is_running = qkey in DAB_RUNNING_TASKS
            md_file = await asyncio.to_thread(_resolve_md)

            if md_file:
                def _get_file_info():
                    try:
                        size = md_file.stat().st_size
                        if size != last_size:
                            return size, md_file.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        pass
                    return last_size, None

                size, content = await asyncio.to_thread(_get_file_info)
                if content is not None:
                    last_size = size
                    parsed = _parse_steps(content)
                    # Only push when the step list actually grew — no duplicate frames
                    if len(parsed["live_steps"]) != last_steps_count:
                        last_steps_count = len(parsed["live_steps"])
                        payload = json.dumps({**parsed, "is_running": is_running})
                        yield f"data: {payload}\n\n"

            if not is_running:
                yield f"event: done\ndata: {json.dumps({'is_running': False})}\n\n"
                break

            await asyncio.sleep(0.8)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # prevent nginx from buffering SSE frames
            "Connection": "keep-alive",
        },
    )


class DabRunAllPayload(BaseModel):
    skip_docker: bool = False
    force_rerun: bool = False
    workers: int = 3  # parallel query workers (keep ≤ 3 to avoid SSL/rate-limit errors)
    runs: int = 5     # passes per query (default 5 for benchmark metrics)
    mode: str = "fresh"  # "fresh" or "continue"
    date: Optional[str] = None  # YYYY-MM-DD
    run_id: Optional[str] = None  # specific archived run_id to continue (e.g. "run_20260617_160102")
    model: Optional[str] = None
    temperature: Optional[float] = None
    dataset_scope: Optional[str] = None


def _parse_qkey(qkey: str):
    parts = qkey.split("_q")
    if len(parts) == 2:
        dataset = parts[0]
        rest = parts[1]
        if "_run" in rest:
            q_id, run_idx = rest.split("_run")
            return dataset, q_id, f"_run{run_idx}"
        else:
            return dataset, rest, ""
    return None


@router.post("/api/dab/stop")
def stop_dab_all():
    """Cancel a running DAB batch job."""
    global DAB_CANCEL_FLAG
    DAB_CANCEL_FLAG.set(True)
    DAB_TOTAL_TASKS.set(0)
    
    # Try to cancel any background tasks managed by TaskManager
    try:
        from agent.app.db.database import SessionLocal
        from agent.app.db.models import TaskRun
        from datetime import datetime
        import time
        import random
        
        for attempt in range(5):
            db = SessionLocal()
            try:
                stale_tasks = db.query(TaskRun).filter(TaskRun.status == "RUNNING").all()
                for t in stale_tasks:
                    t.status = "FAILED"
                    t.error_message = "Cancelled by user"
                    t.updated_at = datetime.utcnow()
                if stale_tasks:
                    db.commit()
                    logger.info(f"Marked {len(stale_tasks)} running SQL tasks as FAILED due to stop request.")
                break
            except Exception as e:
                if "locked" in str(e).lower() and attempt < 4:
                    time.sleep(random.uniform(0.1, 0.5))
                    continue
                logger.error(f"Failed to cancel running task runs in DB (attempt {attempt + 1}): {e}")
                break
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Failed to cancel background tasks: {e}")
        
    # Log any interrupted running tasks before clearing
    running_queries = list(DAB_RUNNING_TASKS)
    if running_queries:
        logger.warning(f"DAB Run stopped by user. The following queries were interrupted and will remain incomplete: {', '.join(running_queries)}")
        
        from agent.app.db.database import SessionLocal
        from agent.app.db.models import Evaluation
        from datetime import datetime
        
        db = SessionLocal()
        try:
            for qkey in running_queries:
                parsed = _parse_qkey(qkey)
                if parsed:
                    dataset, query_id, run_suffix = parsed
                    existing = db.query(Evaluation).filter(
                        Evaluation.dataset == dataset,
                        Evaluation.query_id == query_id,
                        Evaluation.run_suffix == run_suffix,
                        Evaluation.run_id == "live"
                    ).first()
                    if not existing:
                        eval_record = Evaluation(
                            dataset=dataset,
                            query_id=query_id,
                            instance_id=f"{dataset}_q{query_id}",
                            run_suffix=run_suffix,
                            passed=None,
                            reason="Incomplete / stopped abruptly",
                            method="dynamic_validate_py",
                            ground_truth="",
                            agent_answer_snippet="Interrupted by user",
                            elapsed_s=None,
                            input_tokens=0,
                            output_tokens=0,
                            timestamp=datetime.now(),
                            run_id="live"
                        )
                        db.add(eval_record)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log interrupted queries: {e}")
        finally:
            db.close()
    else:
        logger.info("DAB Run stopped by user. No queries were active.")

    # Clear the running tasks set so the UI instantly stops polling
    DAB_RUNNING_TASKS.clear()
    DAB_EXECUTING_TASKS.clear()
    
    return {"message": "Stop requested. Running queries will finish gracefully."}

# Helper functions for dynamic database recovery from archive folders
def parse_evaluation_from_md(md_path: Path) -> dict:
    content = md_path.read_text(encoding="utf-8", errors="replace")
    
    passed = False
    reason = "Incomplete / stopped abruptly"
    
    match = re.search(r"DAB Evaluation:\s*(PASSED|FAILED)(?:\s*\|\s*(.*))?", content)
    if match:
        passed = (match.group(1) == "PASSED")
        reason = match.group(2).strip() if match.group(2) else ("Passed" if passed else "Failed")
    else:
        err_match = re.search(r"DAB query failed:\s*(.*)", content)
        if err_match:
            passed = False
            reason = err_match.group(1).strip()
            
    elapsed_s = 0.0
    lat_match = re.search(r"Latency:\s*(\d+\.?\d*)s", content)
    if lat_match:
        elapsed_s = float(lat_match.group(1))
    else:
        lat_match = re.search(r"elapsed_s:\s*(\d+\.?\d*)", content)
        if lat_match:
            elapsed_s = float(lat_match.group(1))
            
    input_tokens = 0
    output_tokens = 0
    token_matches = re.findall(r"Tokens:\s*(\d+)\s*In\s*/\s*(\d+)\s*Out", content, re.IGNORECASE)
    sum_in = 0
    sum_out = 0
    for match in token_matches:
        sum_in += int(match[0])
        sum_out += int(match[1])
        
    if sum_in > 0 or sum_out > 0:
        input_tokens = sum_in
        output_tokens = sum_out
    else:
        in_match = re.search(r"Input Tokens:\s*(\d+)", content, re.IGNORECASE)
        if in_match:
            input_tokens = int(in_match.group(1))
        out_match = re.search(r"Output Tokens:\s*(\d+)", content, re.IGNORECASE)
        if out_match:
            output_tokens = int(out_match.group(1))
        
    mtime = os.path.getmtime(md_path)
    dt = datetime.fromtimestamp(mtime)
    
    return {
        "passed": passed,
        "reason": reason,
        "elapsed_s": elapsed_s,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "timestamp": dt
    }

def rebuild_run_database_records(db, run_id: str, username: str):
    logger.info(f"Rebuilding database records for archived run: {run_id} (user={username})")
    from agent.app.core.config import get_user_dab_results_dir
    
    # Identify directories to scan (user-scoped first, then legacy fallback)
    dirs_to_scan = []
    user_archive = get_user_dab_results_dir(username) / "_archive" / run_id
    if user_archive.exists():
        dirs_to_scan.append(user_archive)
    legacy_archive = DAB_RESULTS_DIR / "_archive" / run_id
    if legacy_archive.exists():
        dirs_to_scan.append(legacy_archive)
        
    if not dirs_to_scan:
        return
        
    queries = _get_dab_queries()
    q_map = {(q["dataset"].lower(), str(q["query_id"])): q for q in queries}
    
    try:
        parts = run_id.split('_')
        ds, ts = parts[1], parts[2]
        run_dt = datetime.strptime(f"{ds} {ts}", "%Y%m%d %H%M%S")
    except Exception:
        run_dt = datetime.fromtimestamp(dirs_to_scan[0].stat().st_mtime)
        
    from agent.app.db.models import Evaluation
    
    seen_slots = set()
    for archive_dir in dirs_to_scan:
        for root, dirs, files in os.walk(archive_dir):
            for f in files:
                if f.endswith(".md"):
                    md_path = Path(root) / f
                    dataset = md_path.parent.name
                    name = md_path.stem
                    
                    run_suffix = ""
                    if "_run" in name:
                        parts = name.split("_run")
                        q_name = parts[0]
                        run_suffix = f"_run{parts[1]}"
                    else:
                        q_name = name
                        
                    query_id = q_name.lower().replace("query", "")
                    
                    # Avoid duplicates across user-scoped and legacy folders
                    slot_key = (dataset.lower(), query_id, run_suffix)
                    if slot_key in seen_slots:
                        continue
                    seen_slots.add(slot_key)
                    
                    try:
                        res = parse_evaluation_from_md(md_path)
                    except Exception as e:
                        logger.error(f"Failed to parse {md_path}: {e}")
                        continue
                        
                    q_info = q_map.get((dataset.lower(), query_id), {})
                    ground_truth = q_info.get("ground_truth", "")
                    
                    ans_file = md_path.parent / f"{name}_answer.txt"
                    agent_answer = ""
                    if ans_file.exists():
                        try:
                            agent_answer = ans_file.read_text(encoding="utf-8").strip()
                        except Exception:
                            pass
                    if not agent_answer and res.get("passed") is False:
                        agent_answer = f"ERROR: {res['reason']}"
                        
                    ts_val = res.get("timestamp") or run_dt
                    
                    eval_record = Evaluation(
                        dataset=dataset,
                        query_id=query_id,
                        instance_id=f"{dataset}_q{query_id}",
                        run_suffix=run_suffix,
                        passed=res["passed"],
                        reason=res["reason"],
                        method="dynamic_validate_py",
                        ground_truth=ground_truth,
                        agent_answer_snippet=agent_answer[:500] if agent_answer else "",
                        elapsed_s=res["elapsed_s"],
                        input_tokens=res["input_tokens"],
                        output_tokens=res["output_tokens"],
                        timestamp=ts_val,
                        run_id=run_id,
                        username=username
                    )
                    db.add(eval_record)
                    
    try:
        db.commit()
        logger.info(f"Successfully rebuilt database records for {run_id}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save rebuilt database records for {run_id}: {e}")


@router.get("/api/dab/runs")
def get_dab_runs(request: Request):
    """Return the list of last 5 runs for the requesting user. Rebuilds are done in background."""
    from agent.app.db.database import SessionLocal
    from agent.app.db.models import Evaluation
    from agent.app.core.config import get_user_dab_results_dir
    import threading
    
    username = _get_username_from_request(request)
    
    archive_base = get_user_dab_results_dir(username) / "_archive"
    archive_runs = []
    if archive_base.exists():
        for item in archive_base.iterdir():
            if item.is_dir() and item.name.startswith("run_"):
                archive_runs.append(item.name)
                
    # Fallback to check legacy archive directory just in case
    legacy_archive_base = DAB_RESULTS_DIR / "_archive"
    if legacy_archive_base.exists():
        for item in legacy_archive_base.iterdir():
            if item.is_dir() and item.name.startswith("run_"):
                if item.name not in archive_runs:
                    archive_runs.append(item.name)
                
    archive_runs = sorted(archive_runs, reverse=True)
    last_5_runs = archive_runs[:5]
    
    db = SessionLocal()
    try:
        import agent.app.dab.dab_evaluator as de
        # A run is only "active" if tasks are genuinely executing right now.
        # DAB_RUN_ID persists after runs finish, so checking it alone causes
        # the green dot to stay lit forever. Gate on DAB_RUNNING_TASKS instead.
        tasks_running = bool(DAB_RUNNING_TASKS)
        active_run_id = de.DAB_RUN_ID if tasks_running else None

        # Identify runs needing rebuild without doing the rebuild synchronously
        runs_needing_rebuild = []
        for run_id in last_5_runs:
            if run_id == active_run_id:
                continue
            count = db.query(Evaluation).filter(
                Evaluation.run_id == run_id,
                Evaluation.username == username
            ).count()
            if count == 0:
                any_count = db.query(Evaluation).filter(Evaluation.run_id == run_id).count()
                if any_count == 0:
                    runs_needing_rebuild.append(run_id)
                
        # Kick off rebuilds in background so they don't block this response
        if runs_needing_rebuild:
            def _bg_rebuild():
                _db = SessionLocal()
                try:
                    for rid in runs_needing_rebuild:
                        rebuild_run_database_records(_db, rid, username)
                except Exception as e:
                    logger.error(f"Background rebuild failed: {e}")
                finally:
                    _db.close()
            threading.Thread(target=_bg_rebuild, daemon=True).start()
        
        runs = []

        # Inject a "Live View" entry only while tasks are genuinely running.
        # When nothing is running tasks_running is False so this block is skipped,
        # meaning the green dot and the Live View row both disappear automatically.
        if tasks_running:
            runs.append({
                "id": "live",
                "label": "Live View",
                "date": "",
                "is_active": True,
            })

        # If there's an active run not yet archived, surface it in the list.
        if active_run_id and active_run_id.startswith("run_"):
            if active_run_id not in last_5_runs:
                last_5_runs.insert(0, active_run_id)
                
        # Only include archived runs that have data for this user, OR is the currently active run
        for run_id in last_5_runs:
            is_active = (run_id == active_run_id)
            user_count = db.query(Evaluation).filter(
                Evaluation.run_id == run_id,
                Evaluation.username == username
            ).count()
            # Include the run if this user has records, or if nobody has records (legacy)
            any_count = db.query(Evaluation).filter(Evaluation.run_id == run_id).count()
            if is_active or user_count > 0 or any_count == 0:
                label = run_id
                date_str = ""
                try:
                    parts = run_id.split('_')
                    if len(parts) >= 3:
                        ds, ts = parts[1], parts[2]
                        date_str = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
                        time_str = f"{ts[:2]}:{ts[2:4]}:{ts[4:6]}"
                        label = f"{date_str} {time_str}"
                except Exception:
                    pass
                runs.append({
                    "id": run_id,
                    "label": f"{label} (Active)" if is_active else label,
                    "date": date_str,
                    "is_active": is_active
                })
            
        return runs
    except Exception as e:
        logger.error(f"Failed to fetch DAB runs for user {username}: {e}")
        return []
    finally:
        db.close()

@router.delete("/api/dab/runs/{date}")
def delete_dab_run(date: str, request: Request):
    """Delete a historical run by date or run_id."""
    from datetime import datetime
    from agent.app.utils.archive import force_delete_dir, force_delete_file
    from agent.app.db.database import SessionLocal
    from agent.app.db.models import Evaluation
    from sqlalchemy import cast, Date
    from agent.app.core.config import get_user_dab_results_dir
    import shutil
    
    username = _get_username_from_request(request)
    user_dab_dir = get_user_dab_results_dir(username)
    
    if date == "all":
        raise HTTPException(status_code=400, detail="Cannot delete 'all' dates.")
        
    db = SessionLocal()
    try:
        if date.startswith("run_"):
            db.query(Evaluation).filter(
                Evaluation.run_id == date,
                Evaluation.username == username
            ).delete(synchronize_session=False)
            db.commit()
            
            # Delete from user-scoped archive
            archive_base = user_dab_dir / "_archive"
            run_folder = archive_base / date
            if run_folder.exists() and run_folder.is_dir():
                force_delete_dir(run_folder)
                
            # Delete from legacy archive fallback
            legacy_run_folder = DAB_RESULTS_DIR / "_archive" / date
            if legacy_run_folder.exists() and legacy_run_folder.is_dir():
                force_delete_dir(legacy_run_folder)
                
            _cached_dab_metrics.cache_clear()
            global _dab_queries_cache
            _dab_queries_cache = None
            return {"message": f"Run {date} deleted."}
            
        elif date == "live":
            db.query(Evaluation).filter(
                Evaluation.username == username,
                ((Evaluation.run_id == "live") | (Evaluation.run_id == None))
            ).delete(synchronize_session=False)
            db.commit()
            
            if user_dab_dir.exists():
                for item in user_dab_dir.iterdir():
                    if item.name != "_archive":
                        if item.is_dir():
                            force_delete_dir(item)
                        else:
                            force_delete_file(item)
                             
            _cached_dab_metrics.cache_clear()
            _dab_queries_cache = None
            return {"message": "Cleared live results."}
            
        else:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=1)
            
            db.query(Evaluation).filter(
                Evaluation.username == username,
                Evaluation.timestamp >= start_dt,
                Evaluation.timestamp < end_dt
            ).delete(synchronize_session=False)
            db.commit()
            
            today = datetime.now().strftime("%Y-%m-%d")
            if date == today:
                if user_dab_dir.exists():
                    for item in user_dab_dir.iterdir():
                        if item.name != "_archive":
                            if item.is_dir():
                                force_delete_dir(item)
                            else:
                                force_delete_file(item)
            else:
                archive_base = user_dab_dir / "_archive"
                if archive_base.exists():
                    for run_folder in archive_base.iterdir():
                        if run_folder.is_dir():
                            try:
                                date_str = run_folder.name.split('_')[1]
                                run_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                                if run_date == date:
                                    force_delete_dir(run_folder)
                            except Exception:
                                pass
                                
                # Also delete matching legacy folders
                legacy_archive_base = DAB_RESULTS_DIR / "_archive"
                if legacy_archive_base.exists():
                    for run_folder in legacy_archive_base.iterdir():
                        if run_folder.is_dir():
                            try:
                                date_str = run_folder.name.split('_')[1]
                                run_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                                if run_date == date:
                                    force_delete_dir(run_folder)
                            except Exception:
                                pass
                                
            _cached_dab_metrics.cache_clear()
            _dab_queries_cache = None
            return {"message": f"Run {date} deleted."}
    except Exception as e:
        logger.error(f"Failed to delete DAB run/date {date} for user {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/api/dab/run_all")
def run_dab_all(request: Request, payload: DabRunAllPayload = DabRunAllPayload()):
    """Trigger a full DAB benchmark run (all pending queries)."""
    from agent.app.dab.dab_evaluator import load_eval_result
    import shutil
    from datetime import datetime
    
    global DAB_CANCEL_FLAG
    DAB_CANCEL_FLAG.set(False)

    from agent.app.db.models import Evaluation
    from agent.app.db.database import SessionLocal
    from datetime import datetime, timedelta

    # Determine the user making the request
    username = _get_username_from_request(request)

    db = SessionLocal()
    completed_keys = set()
    
    # Target date parsing (timezone agnostic matching rest of app)
    run_date_str = payload.date or datetime.now().strftime("%Y-%m-%d")
    start_dt = datetime.strptime(run_date_str, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=1)

    # Generate or reuse timestamped run_id for the current run
    # Capture a single fixed "now" so that run_id and the archive fallback
    # always reference the SAME moment — no second datetime.now() call.
    _run_start_time = datetime.now()
    if payload.mode == "continue" and payload.run_id:
        run_id = payload.run_id
    else:
        run_id = _run_start_time.strftime("run_%Y%m%d_%H%M%S")

    # Set run date + username override in dab_evaluator module so all new evals
    # are timestamped correctly and attributed to this user.
    import agent.app.dab.dab_evaluator as de
    de.DAB_RUN_DATE = run_date_str
    de.DAB_RUN_ID = run_id
    de.DAB_RUN_USERNAME = username

    try:
        # 1. Purge any incomplete/corrupted evaluations for the target date (user-scoped, optionally dataset-scoped)
        purge_query = db.query(Evaluation).filter(
            Evaluation.timestamp >= start_dt,
            Evaluation.timestamp < end_dt,
            Evaluation.username == username,
            (Evaluation.passed == None) | (Evaluation.elapsed_s == None)
        )
        if payload.dataset_scope:
            purge_query = purge_query.filter(Evaluation.dataset == payload.dataset_scope)
            
        deleted_count = purge_query.delete(synchronize_session=False)
        db.commit()
        if deleted_count > 0:
            scope_info = f" (scope={payload.dataset_scope})" if payload.dataset_scope else ""
            logger.info(f"Purged {deleted_count} incomplete/aborted evaluation records for {run_date_str}{scope_info} (user={username}).")

        if payload.mode == "continue":
            logger.info(f"DAB run_all: Continuing previous incomplete run for {run_date_str} (user={username}).")
            # Retrieve already completed runs for this user to skip them.
            # Check both live records AND archived run_id records (for when a run_ id was selected).
            completed_query = db.query(Evaluation).filter(
                Evaluation.username == username,
                Evaluation.passed != None,
                Evaluation.elapsed_s != None
            ).filter(
                # Match either by date range OR by specific run_id
                (
                    (Evaluation.timestamp >= start_dt) & (Evaluation.timestamp < end_dt)
                ) | (
                    (payload.run_id != None) & (Evaluation.run_id == payload.run_id)
                )
            )
            if payload.dataset_scope:
                completed_query = completed_query.filter(Evaluation.dataset == payload.dataset_scope)
            completed_records = completed_query.all()
            for rec in completed_records:
                completed_keys.add((rec.dataset, str(rec.query_id), rec.run_suffix or ""))
            logger.info(f"Continue mode: {len(completed_keys)} already-completed slots found for user={username}.")
        else:
            logger.info(f"DAB run_all: Starting a fresh run for {run_date_str} (user={username}).")
            # Clear LangChain LLM SQLite cache so stale classification/routing
            # responses from prior runs don't short-circuit the new run.
            from agent.app.core.config import CONFIG_DIR as _cfg_dir
            _llm_cache_db = _cfg_dir.parent / ".langchain_cache.db"
            if _llm_cache_db.exists():
                try:
                    _llm_cache_db.unlink()
                    logger.info("Cleared LangChain LLM cache (.langchain_cache.db) for fresh DAB run.")
                except Exception as _ce:
                    logger.warning(f"Could not clear LangChain LLM cache: {_ce}")
            # 1. Check if there are live database records to archive
            first_record_query = db.query(Evaluation).filter(
                Evaluation.username == username,
                (Evaluation.run_id == "live") | (Evaluation.run_id == None)
            )
            if payload.dataset_scope:
                first_record_query = first_record_query.filter(Evaluation.dataset == payload.dataset_scope)
            first_record = first_record_query.order_by(Evaluation.timestamp.asc()).first()
            
            # 2. Check if there are files on disk to archive in user's results folder
            from agent.app.core.config import get_user_dab_results_dir
            user_dab_dir = get_user_dab_results_dir(username)
            files_to_move = []
            if user_dab_dir.exists():
                for item in user_dab_dir.iterdir():
                    if item.name != "_archive":
                        if not payload.dataset_scope or item.name == payload.dataset_scope:
                            files_to_move.append(item)

            # 3. Only archive if there is actually data to archive
            if first_record or files_to_move:
                if first_record and first_record.timestamp:
                    archive_run_id = first_record.timestamp.strftime("run_%Y%m%d_%H%M%S")
                else:
                    # Fallback: use the pre-captured start time minus 1 second so it
                    # is always strictly earlier than run_id and never triggers a
                    # second datetime.now() call that shows up as a separate UI entry.
                    from datetime import timedelta as _td
                    _archive_time = _run_start_time - _td(seconds=1)
                    archive_run_id = _archive_time.strftime("run_%Y%m%d_%H%M%S")

                # Move files on disk to user's archive
                archive_dir = user_dab_dir / "_archive" / archive_run_id
                archive_dir.mkdir(parents=True, exist_ok=True)
                for item in files_to_move:
                    try:
                        shutil.move(str(item), str(archive_dir / item.name))
                    except Exception as e:
                        logger.error(f"Failed to archive file/folder {item}: {e}")

                # Update this user's live database records to have the archived run_id
                update_query = db.query(Evaluation).filter(
                    Evaluation.username == username,
                    (Evaluation.run_id == "live") | (Evaluation.run_id == None)
                )
                if payload.dataset_scope:
                    update_query = update_query.filter(Evaluation.dataset == payload.dataset_scope)
                updated = update_query.update({Evaluation.run_id: archive_run_id}, synchronize_session=False)
                db.commit()
                logger.info(f"Archived previous run to {archive_run_id} ({updated} DB records, {len(files_to_move)} folders/files).")
            else:
                logger.info("Nothing to archive from previous runs.")
            
    except Exception as e:
        logger.error(f"Failed to setup DAB run (mode={payload.mode}, date={run_date_str}, user={username}): {e}")
    finally:
        db.close()

    queries = _get_dab_queries()
    if not queries:
        return {"error": "No queries found. Check DAB repo path."}

    # Filter by dataset scope if provided
    if payload.dataset_scope:
        queries = [q for q in queries if q["dataset"] == payload.dataset_scope]

    to_run = []
    for q in queries:
        if payload.skip_docker and q["needs_docker"]:
            continue
        # Global runs always queue payload.runs passes for each question
        for i in range(payload.runs):
            run_sfx = "" if i == 0 else f"_run{i}"
            if payload.mode == "continue" and (q["dataset"], str(q["query_id"]), run_sfx) in completed_keys:
                continue

            run_instance = q.copy()
            if i > 0:
                run_instance["instance_id"] = f"{q['instance_id']}_run{i}"
            run_instance["run_number"] = i
            qkey = run_instance["instance_id"]
            
            if qkey not in DAB_RUNNING_TASKS:
                to_run.append(run_instance)
                DAB_RUNNING_TASKS.add(qkey)

    if not to_run:
        return {
            "message": "All queries already evaluated. Use force_rerun=true to re-run.",
            "count": 0,
        }

    DAB_TOTAL_TASKS.set(len(to_run))
    num_workers = max(1, min(payload.workers, 50))  # clamp to [1, 50] — supports high-concurrency runs

    def _run_one(q):
        global DAB_CANCEL_FLAG
        if DAB_CANCEL_FLAG:
            DAB_RUNNING_TASKS.discard(q["instance_id"])
            return
        qkey = q["instance_id"]
        DAB_EXECUTING_TASKS.add(qkey)
        try:
            from agent.app.dab.dab_orchestrator import run_dab_query
            from agent.app.utils.llm import CB_RESET_AFTER_S, CB_MAX_WAIT_S
            import time as _time

            # Patterns that identify a transient Bedrock connectivity failure.
            # These may escape run_dab_query if _cb_wait_until_clear() finally
            # exhausted its patience budget (i.e. Bedrock was down >10 minutes).
            _TRANSIENT = (
                "EndpointConnectionError", "ReadTimeoutError",
                "Connection was closed", "Could not connect",
                "ThrottlingException", "ServiceUnavailableException",
                "circuit breaker",
            )

            # Safety-net: retry the whole query if a transient Bedrock error
            # escapes (should be rare now that generate() blocks internally).
            _MAX_OUTER_RETRIES = 3
            for _attempt in range(_MAX_OUTER_RETRIES):
                try:
                    run_dab_query(
                        q,
                        run_number=q.get("run_number", 0),
                        model=payload.model,
                        temperature=payload.temperature
                    )
                    break   # completed (pass or fail) — don't retry
                except Exception as exc:
                    exc_str = str(exc)
                    is_transient = any(p in exc_str for p in _TRANSIENT)
                    if not is_transient or _attempt >= _MAX_OUTER_RETRIES - 1:
                        logger.error(
                            f"[DABBatch] {qkey}: unrecoverable error on attempt "
                            f"{_attempt + 1}/{_MAX_OUTER_RETRIES}: {type(exc).__name__}: {exc}"
                        )
                        break   # give up — result already written by run_dab_query's except
                    if DAB_CANCEL_FLAG:
                        break
                    wait_s = min(CB_RESET_AFTER_S + 10, 130.0)
                    logger.warning(
                        f"[DABBatch] {qkey}: transient error escaped run_dab_query "
                        f"({type(exc).__name__}) — waiting {wait_s:.0f}s before "
                        f"outer retry {_attempt + 1}/{_MAX_OUTER_RETRIES}."
                    )
                    _time.sleep(wait_s)
                    if DAB_CANCEL_FLAG:
                        break
        except Exception:
            pass
        finally:
            DAB_EXECUTING_TASKS.discard(qkey)
            DAB_RUNNING_TASKS.discard(qkey)

    def _run_batch():
        from concurrent.futures import ThreadPoolExecutor as _Pool, as_completed as _done
        global DAB_CANCEL_FLAG

        logger.info(
            f"DAB ThreadPoolExecutor starting batch of {len(to_run)} queries with {num_workers} workers. "
            f"Model override: {payload.model}, Temperature override: {payload.temperature}"
        )

        with _Pool(max_workers=num_workers) as pool:
            futures = {pool.submit(_run_one, q): q for q in to_run}
            for fut in _done(futures):
                if DAB_CANCEL_FLAG:
                    for remaining in futures:
                        remaining.cancel()
                    # Discard any still-queued keys
                    for q in futures.values():
                        DAB_RUNNING_TASKS.discard(q["instance_id"])
                    break
                try:
                    fut.result()
                except Exception:
                    pass

        global _dab_queries_cache
        _dab_queries_cache = None
        _cached_dab_metrics.cache_clear()
        
        # Reset run date override
        import agent.app.dab.dab_evaluator as de
        de.DAB_RUN_DATE = None
        de.DAB_RUN_ID = None
        DAB_TOTAL_TASKS.set(0)

        # ── Auto Self-Improvement (Fix 1) ───────────────────────────────────
        # After every benchmark batch completes, automatically extract rules from
        # failures and promote them to dynamic_lessons.json so the pipeline learns
        # without any manual intervention.
        if not DAB_CANCEL_FLAG:
            def _auto_self_improve():
                try:
                    from agent.app.core.rules.self_improving_loop import SelfImprovingLoop
                    from agent.app.core.config import DAB_REPO as _DAB_REPO
                    logger.info("[AutoSelfImprove] Batch complete — starting self-improvement round.")
                    sil = SelfImprovingLoop(dab_repo=str(_DAB_REPO))
                    result = sil.run_daily()
                    status = result.get("status", "unknown")
                    run_info = result.get("run", {})
                    rounds = run_info.get("rounds", [])
                    logger.info(
                        f"[AutoSelfImprove] Completed. status={status}, "
                        f"rounds={len(rounds)}, "
                        f"pass_rate={run_info.get('pass_rate', 'N/A')}%"
                    )
                    for r in rounds:
                        logger.info(
                            f"[AutoSelfImprove] Round {r['round']}: {r['status']} "
                            f"delta={r.get('delta', 0):+d} rules_added={r.get('new_rules_added', 0)}"
                        )
                except Exception as _sie:
                    import traceback as _tb
                    logger.error(f"[AutoSelfImprove] Failed: {_sie}\n{_tb.format_exc()}")

            import threading as _threading
            _si_thread = _threading.Thread(target=_auto_self_improve, daemon=True, name="auto_self_improve")
            _si_thread.start()
            logger.info("[AutoSelfImprove] Self-improvement thread launched.")

    logger.info(
        f"DAB run_all: Submitting batch run with {len(to_run)} queries to execution pool. "
        f"Workers={num_workers}, scope={payload.dataset_scope}, model={payload.model}, temp={payload.temperature}"
    )
    EXECUTION_POOL.submit(_run_batch)
    return {
        "message": f"Started DAB batch run: {len(to_run)} queries queued",
        "count": len(to_run),
        "skip_docker": payload.skip_docker,
    }


@router.get("/api/dab/results/recent")
def get_dab_recent_results(request: Request, limit: int = 15, date: str = "all", run_id: Optional[str] = None, force: bool = False):
    username = _get_username_from_request(request)
    run_id = _resolve_live_run_id(run_id, username)
    from agent.app.db.database import SessionLocal
    from agent.app.db.models import Evaluation
    from datetime import datetime

    username = _get_username_from_request(request)
    db = SessionLocal()
    try:
        query = db.query(Evaluation).filter(Evaluation.username == username)
        if run_id is not None:
            if run_id == "all":
                pass
            elif run_id == "live":
                query = query.filter((Evaluation.run_id == "live") | (Evaluation.run_id == None))
            else:
                query = query.filter(Evaluation.run_id == run_id)
        elif date != "all":
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=1)
            query = query.filter(
                Evaluation.timestamp >= start_dt,
                Evaluation.timestamp < end_dt
            )
            
        records = query.order_by(Evaluation.timestamp.desc()).limit(limit).all()
        
        recent = []
        for rec in records:
            passed = rec.passed
            total_tokens = (rec.input_tokens or 0) + (rec.output_tokens or 0)
            timestamp = rec.timestamp.isoformat() if rec.timestamp else ""
            
            recent.append(
                {
                    "id": rec.instance_id or f"{rec.dataset}_q{rec.query_id}",
                    "db": rec.dataset,
                    "status": "success" if passed else "error",
                    "gold_status": "gold_pass" if passed else "gold_fail",
                    "latency": round(rec.elapsed_s or 0, 1),
                    "complexity": "medium",
                    "complexity_type": "Unclassified",
                    "complexity_score": 0.0,
                    "corrections": 0,
                    "critic_rounds": 0,
                    "rows": 0,
                    "timestamp": timestamp,
                    "total_tokens": total_tokens,
                    "cost": round(total_tokens * 0.000003, 6),
                    "reason": rec.reason or "",
                }
            )
        return recent
    except Exception as e:
        logger.error(f"Failed to load recent dab results: {e}")
        return []
    finally:
        db.close()


@router.get("/api/dab/status")
def get_dab_run_status():
    """Get which DAB queries are currently running from DB."""
    from agent.app.services.task_manager import TaskManager
    running_tasks = TaskManager.get_running_tasks()
    
    # Also check the old memory-based set just in case some tasks didn't migrate
    all_running = list(DAB_RUNNING_TASKS) + [t["target"] for t in running_tasks]
    
    # Calculate global completion progress for the active batch
    total_queries = DAB_TOTAL_TASKS.get()
    if not total_queries:
        queries = _get_dab_queries()
        total_queries = len(queries) * 5
    
    # Completed = total queued minus what's still in the running set.
    # This is accurate because run_all adds ALL slots to DAB_RUNNING_TASKS upfront
    # and removes each slot as it finishes, so the difference is exact.
    running_count = len(all_running)
    if running_count > 0:
        completed_queries = max(0, total_queries - running_count)
    else:
        completed_queries = 0
        
    executing = list(DAB_EXECUTING_TASKS)
    if not executing and all_running:
        executing = all_running[:1]
    
    return {
        "running": all_running,
        "executing": executing,
        "count": len(all_running),
        "runner_active": len(running_tasks) > 0,
        "total": total_queries,
        "completed": completed_queries
    }


@router.get("/api/dab/repo_check")
def check_dab_repo():
    """Check if the DataAgentBench repo is available and cloned."""
    from pathlib import Path

    repo_path = Path(DAB_REPO_PATH_DEFAULT)
    exists = repo_path.exists()
    query_dirs = []
    if exists:
        query_dirs = [
            d.name
            for d in repo_path.iterdir()
            if d.is_dir() and d.name.startswith("query_")
        ]
    return {
        "repo_path": DAB_REPO_PATH_DEFAULT,
        "exists": exists,
        "query_datasets_found": len(query_dirs),
        "datasets": sorted(query_dirs),
    }


@router.get("/api/improvement/status")
def get_improvement_status():
    """Return self-improvement pipeline history and current rule counts."""
    log_path = MEMORY_DIR / "improvement_log.json"
    lessons_path = MEMORY_DIR / "dynamic_lessons.json"

    log: Dict[str, Any] = {}
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = {}

    rule_counts: Dict[str, int] = {
        "ACTIVE": 0,
        "CANDIDATE": 0,
        "REJECTED": 0,
        "INACTIVE": 0,
    }
    if lessons_path.exists():
        try:
            with open(lessons_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
            for r in rules:
                s = r.get("status", "UNKNOWN")
                rule_counts[s] = rule_counts.get(s, 0) + 1
        except Exception:
            pass

    # Build accuracy trend: one point per daily run entry
    accuracy_trend = []
    for run in log.get("runs", []):
        accuracy_trend.append(
            {
                "date": run.get("date", ""),
                "pass_rate": run.get("pass_rate", 0),
                "final_passes": run.get("final_passes", 0),
                "total": run.get("total", 0),
            }
        )

    # Flatten all rounds across all runs for recent_runs table
    recent_rounds = []
    for run in log.get("runs", []):
        for r in run.get("rounds", []):
            recent_rounds.append(
                {
                    "date": r.get("date", run.get("date", "")),
                    "round": r.get("round", 1),
                    "status": r.get("status", ""),
                    "delta": r.get("delta", 0),
                    "passes_before": r.get("passes_before", 0),
                    "passes_after": r.get("passes_after", 0),
                    "pass_rate": r.get("pass_rate", 0),
                    "new_rules_added": r.get("new_rules_added", 0),
                    "elapsed_s": r.get("elapsed_s", 0),
                    "total": r.get("total", 0),
                }
            )

    return {
        "saturated": log.get("saturated", False),
        "last_run": log.get("last_run"),
        "total_rounds": log.get("total_rounds", 0),
        "baseline_pass_rate": log.get("baseline_pass_rate"),
        "rule_counts": rule_counts,
        "accuracy_trend": accuracy_trend[-30:],
        "recent_runs": recent_rounds[-15:],
    }


@router.post("/api/improvement/run")
async def trigger_improvement_run(background_tasks: BackgroundTasks):
    """Trigger a self-improvement run in the background (respects daily cap)."""
    from agent.app.core.config import DAB_REPO as DAB_REPO_PATH

    # Snapshot current lessons before mutating them so rollback is always available
    rollback = LessonRollback(
        lessons_path=MEMORY_DIR / "dynamic_lessons.json",
        snapshot_dir=MEMORY_DIR / "lessons_snapshots",
    )
    snapshot_name = rollback.save_snapshot()

    def _run():
        try:
            from agent.app.core.rules.self_improving_loop import SelfImprovingLoop

            loop = SelfImprovingLoop(dab_repo=str(DAB_REPO_PATH))
            loop.run_daily()
        except Exception as e:
            import traceback as tb

            logger.error(f"Improvement run failed: {e}\n{tb.format_exc()}")

    background_tasks.add_task(_run)
    return {
        "message": "Self-improvement run started in background. Check /api/improvement/status for results.",
        "snapshot": snapshot_name,
    }


@router.get("/api/improvement/snapshots")
def list_lesson_snapshots():
    """List all available lesson snapshots that can be used for rollback."""
    rollback = LessonRollback(
        lessons_path=MEMORY_DIR / "dynamic_lessons.json",
        snapshot_dir=MEMORY_DIR / "lessons_snapshots",
    )
    snapshots = rollback.list_snapshots()
    return {
        "count": len(snapshots),
        "snapshots": snapshots,
        "rollback_endpoint": "POST /api/improvement/rollback?version=YYYYMMDD_HHMMSS",
    }


@router.post("/api/improvement/rollback")
def rollback_lessons(version: str):
    """
    Atomically restore dynamic_lessons.json from the specified snapshot version.

    ``version`` is the snapshot stem returned by GET /api/improvement/snapshots
    (format: ``YYYYMMDD_HHMMSS``).  The live lessons file is replaced atomically
    using write-then-rename so in-flight readers are never disrupted.
    """
    rollback = LessonRollback(
        lessons_path=MEMORY_DIR / "dynamic_lessons.json",
        snapshot_dir=MEMORY_DIR / "lessons_snapshots",
    )
    success = rollback.rollback_to(version)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot '{version}' not found. "
            "Use GET /api/improvement/snapshots to list available versions.",
        )
    return {
        "success": True,
        "rolled_back_to": version,
        "message": "Lessons restored. The pipeline will use the rolled-back rules immediately.",
    }


# ---------------------------------------------------------------------------
# LangSmith Evaluators API
# ---------------------------------------------------------------------------

DAB_RESULTS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "results" / "dab"
)

_langsmith_eval_running = False


@router.get("/api/langsmith/status")
def langsmith_status():
    """
    Return LangSmith connection status, project info, and dataset stats.
    Also shows per-evaluator aggregate scores from stored DAB eval results.
    """
    from agent.app.core.langsmith_evaluators import (
        _client,
        DATASET_NAME,
        run_all_evaluators,
    )

    status = {
        "connected": False,
        "project": os.getenv("LANGCHAIN_PROJECT", "TT_SQL_V2"),
        "tracing_enabled": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
        "dataset_name": DATASET_NAME,
        "dataset_examples": 0,
        "eval_running": _langsmith_eval_running,
        "evaluator_summaries": {},
    }

    try:
        projects = {p.name: str(p.id) for p in _client.list_projects()}
        status["connected"] = True
        status["project_id"] = projects.get(status["project"])
        status["all_projects"] = list(projects.keys())

        # Dataset count
        try:
            dataset = _client.read_dataset(dataset_name=DATASET_NAME)
            status["dataset_examples"] = sum(
                1 for _ in _client.list_examples(dataset_id=str(dataset.id))
            )
        except Exception:
            status["dataset_examples"] = 0

    except Exception as e:
        status["error"] = str(e)

    # Aggregate evaluator scores over stored eval JSON records
    agg: dict[str, list] = {}
    if DAB_RESULTS_PATH.exists():
        for eval_file in DAB_RESULTS_PATH.glob("**/*.json"):
            try:
                rec = json.loads(eval_file.read_text(encoding="utf-8"))
                feedbacks = run_all_evaluators(rec)
                for fb in feedbacks:
                    key = fb["key"]
                    score = fb.get("score")
                    if score is not None:
                        agg.setdefault(key, []).append(score)
            except Exception:
                continue

    for key, scores in agg.items():
        if scores:
            status["evaluator_summaries"][key] = {
                "mean": round(sum(scores) / len(scores), 3),
                "n": len(scores),
                "flagged": sum(1 for s in scores if s > 0.5),
            }

    return status


@router.post("/api/langsmith/build_dataset")
async def build_langsmith_dataset(background_tasks: BackgroundTasks):
    """Create/update the 'DAB Benchmark' LangSmith dataset with all 54 queries."""

    def _build():
        try:
            from agent.app.core.langsmith_evaluators import build_dab_dataset

            dataset_id = build_dab_dataset()
            logger.info(f"LangSmith dataset built: {dataset_id}")
        except Exception as e:
            logger.error(f"LangSmith dataset build failed: {e}")

    background_tasks.add_task(_build)
    return {
        "message": "Building DAB Benchmark dataset in LangSmith. Check /api/langsmith/status for progress."
    }


@router.post("/api/langsmith/run_eval")
async def run_langsmith_eval(background_tasks: BackgroundTasks):
    """
    Run a full offline LangSmith experiment over the DAB Benchmark dataset
    applying all 8 evaluators. Results appear in LangSmith under TT_SQL_V2 project.
    """
    global _langsmith_eval_running
    if _langsmith_eval_running:
        return {
            "message": "Evaluation already running. Check LangSmith dashboard for progress."
        }

    def _run():
        global _langsmith_eval_running
        _langsmith_eval_running = True
        try:
            from agent.app.core.langsmith_evaluators import run_langsmith_experiment

            summary = run_langsmith_experiment(experiment_prefix="TT_SQL_V2")
            logger.info(f"LangSmith experiment complete: {summary}")
        except Exception as e:
            import traceback as tb

            logger.error(f"LangSmith eval failed: {e}\n{tb.format_exc()}")
        finally:
            _langsmith_eval_running = False

    background_tasks.add_task(_run)
    return {
        "message": "LangSmith evaluation started. All 8 evaluators running over 54 DAB queries.",
        "evaluators": [
            "correctness",
            "hallucination",
            "pii_leakage",
            "prompt_injection",
            "toxicity",
            "bias_fairness",
            "perceived_error",
            "user_satisfaction",
        ],
        "view_at": "https://smith.langchain.com",
    }


@router.get("/api/langsmith/scores")
def get_langsmith_scores():
    """
    Return per-query evaluator scores from stored DAB eval JSON records.
    Used by the UI to show the evaluator scorecard.
    """
    rows = []
    if not DAB_RESULTS_PATH.exists():
        return {"scores": rows}

    from agent.app.core.langsmith_evaluators import run_all_evaluators

    for eval_file in sorted(DAB_RESULTS_PATH.glob("**/*.json")):
        try:
            rec = json.loads(eval_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        feedbacks = run_all_evaluators(rec)
        row = {
            "instance_id": rec.get("instance_id", ""),
            "dataset": rec.get("dataset", ""),
            "query_id": rec.get("query_id", 0),
            "passed": rec.get("passed", False),
        }
        for fb in feedbacks:
            row[fb["key"]] = fb.get("score")
        rows.append(row)

    return {"scores": rows, "total": len(rows)}


@router.get("/api/dab/schema/{dataset}")
def get_dab_schema(dataset: str):
    """Retrieve all tables and columns for a given DAB dataset."""
    queries = _get_dab_queries()
    db_clients = {}
    db_description = ""
    for q in queries:
        if q["dataset"].lower() == dataset.lower():
            db_clients = q.get("db_clients", {})
            db_description = q.get("db_description", "")
            break
            
    if not db_clients:
        return {"error": f"No database clients found for dataset '{dataset}'"}
        
    schema_info = {}
    
    for client_name, client in db_clients.items():
        db_type = client.get("db_type", "").lower()
        db_path_str = client.get("db_path")
        if not db_path_str:
            continue
        db_path = Path(db_path_str)
        if not db_path.exists():
            continue
            
        if db_type == "sqlite":
            try:
                import sqlite3
                conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=2.0)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [t[0] for t in cursor.fetchall()]
                
                db_schema = {}
                for table in tables:
                    cursor.execute(f"PRAGMA table_info(\"{table}\");")
                    cols = cursor.fetchall()
                    db_schema[table] = [
                        {
                            "name": c[1],
                            "type": c[2],
                            "notnull": bool(c[3]),
                            "pk": bool(c[5])
                        }
                        for c in cols
                    ]
                conn.close()
                schema_info[client_name] = {
                    "db_type": "sqlite",
                    "tables": db_schema
                }
            except Exception as e:
                logger.error(f"Failed to load SQLite schema: {e}")
        elif db_type == "duckdb":
            try:
                import duckdb
                conn = duckdb.connect(str(db_path), read_only=True)
                tables_res = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main';").fetchall()
                tables = [t[0] for t in tables_res]
                
                db_schema = {}
                for table in tables:
                    cols_res = conn.execute(f"DESCRIBE \"{table}\";").fetchall()
                    db_schema[table] = [
                        {
                            "name": c[0],
                            "type": c[1],
                            "notnull": c[2] == "NO",
                            "pk": c[3] == "PRI" or "key" in str(c[4]).lower()
                        }
                        for c in cols_res
                    ]
                conn.close()
                schema_info[client_name] = {
                    "db_type": "duckdb",
                    "tables": db_schema
                }
            except Exception as e:
                logger.error(f"Failed to load DuckDB schema: {e}")
                
    return {
        "dataset": dataset,
        "description": db_description,
        "schema": schema_info
    }


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8010)

