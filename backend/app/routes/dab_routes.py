from fastapi import APIRouter, HTTPException, BackgroundTasks
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

from backend.app.core.config import DAB_RESULTS_DIR
from backend.app.core.dependencies import EXECUTION_POOL

router = APIRouter()

# ===========================================================================
# DAB (DataAgentBench) Endpoints â€” completely isolated from Spider2-Lite code
# ===========================================================================

from backend.app.core.config import DAB_REPO as _DAB_REPO

DAB_REPO_PATH_DEFAULT = str(_DAB_REPO)
DAB_RESULTS_BASE = DAB_RESULTS_DIR
DAB_RUNNING_TASKS: set = set()
DAB_CANCEL_FLAG: bool = False
_dab_queries_cache = None


def _get_dab_queries():
    """Lazy-load and cache all DAB queries from the repo."""
    global _dab_queries_cache
    if _dab_queries_cache is not None:
        return _dab_queries_cache
    try:
        from backend.app.dab.benchmark_loader import load_all_queries

        _dab_queries_cache = load_all_queries(DAB_REPO_PATH_DEFAULT)
    except Exception:
        _dab_queries_cache = []
    return _dab_queries_cache


def _dab_query_status(dataset: str, query_id: str, date: str = "all") -> Dict[str, Any]:
    """Get the live status of a specific DAB query execution."""
    query_id = query_id.lower().replace("query", "")
    from backend.app.dab.dab_evaluator import load_eval_result
    qkey = f"{dataset}_q{query_id}"

    if qkey in DAB_RUNNING_TASKS:
        return {"status": "running", "passed": None, "reason": "", "evaluated": False, "latency": 0}

    eval_result = load_eval_result(dataset, query_id, date=date)
    if eval_result is None:
        return {"status": "pending", "passed": None, "reason": "", "evaluated": False, "latency": 0}

    return {
        "status": "passed" if eval_result.get("passed") else "failed",
        "passed": eval_result.get("passed"),
        "reason": eval_result.get("reason", ""),
        "method": eval_result.get("method", ""),
        "timestamp": eval_result.get("timestamp", ""),
        "agent_answer": eval_result.get("agent_answer_snippet", ""),
        "ground_truth": eval_result.get("ground_truth", ""),
        "evaluated": True,
        "latency": eval_result.get("elapsed_s", 0),
        "input_tokens": eval_result.get("input_tokens", 0),
        "output_tokens": eval_result.get("output_tokens", 0),
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
def _cached_dab_metrics(date: str, ttl_hash: int):
    """Compute DAB accuracy metrics with TTL caching."""
    try:
        from backend.app.dab.dab_evaluator import compute_accuracy

        queries = _get_dab_queries()
        metrics = compute_accuracy(queries, date=date)
        
        # Format and attach additional fields to match Spider dashboard
        evaluated = metrics.get("evaluated", 0)
        total_time = metrics.get("total_elapsed_time_s", 0)
        total_input_tokens = metrics.get("total_input_tokens", 0)
        total_output_tokens = metrics.get("total_output_tokens", 0)
        total_tokens = total_input_tokens + total_output_tokens
        
        # Bedrock pricing model cost estimate ($0.15/1M input, $0.60/1M output)
        cost = (total_input_tokens * 0.15 / 1000000.0) + (total_output_tokens * 0.60 / 1000000.0)
        
        metrics["passed"] = metrics.get("queries_passed_atk", 0)
        metrics["failed"] = evaluated - metrics["passed"]
        metrics["avg_latency"] = f"{total_time / evaluated:.1f}s" if evaluated > 0 else "0.0s"
        metrics["avg_tokens_per_agent"] = f"{int(total_tokens / evaluated):,} tokens" if evaluated > 0 else "0 tokens"
        metrics["total_tokens"] = f"{total_tokens / 1000000:.2f}M" if total_tokens >= 1000000 else f"{total_tokens / 1000:.1f}K" if total_tokens > 0 else "0"
        metrics["total_cost"] = f"${cost:.4f}"
        metrics["avg_cost_per_query"] = f"${(cost / evaluated):.4f}" if evaluated > 0 else "$0.0000"
        
        return metrics
    except Exception as e:
        return {
            "error": str(e),
            "total_queries": 0,
            "evaluated": 0,
            "pending": 0,
            "passed": 0,
            "failed": 0,
            "pass_at_1": 0.0,
            "pass_at_1_pct": "0.0%",
            "per_dataset": {},
            "avg_latency": "0.0s",
            "avg_tokens_per_agent": "0 tokens",
            "total_cost": "$0.0000",
            "avg_cost_per_query": "$0.0000",
        }


@router.get("/api/dab/databases")
def get_dab_databases(date: str = "all"):
    """Return DAB datasets formatted like Spider databases."""
    metrics = _cached_dab_metrics(date, _get_ttl_hash(15))
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
def get_dab_queries_by_db(dataset: str, date: str = "all"):
    """Return queries for a specific DAB dataset."""
    queries = _get_dab_queries()
    db_queries = [q for q in queries if q.get("dataset") == dataset]
    
    result = []
    for q in db_queries:
        status_info = _dab_query_status(q["dataset"], q["query_id"], date=date)
        dbtypes = list({cfg.get("db_type", "?") for cfg in q.get("db_clients", {}).values()})
        
        # Calculate tokens and cost
        input_t = status_info.get("input_tokens", 0) or 0
        output_t = status_info.get("output_tokens", 0) or 0
        total_tokens = input_t + output_t
        cost = (input_t * 0.15 / 1000000.0) + (output_t * 0.60 / 1000000.0)
        
        # Calculate rows count from CSV (cached)
        rows_count = 0
        csv_file = DAB_RESULTS_BASE / q["dataset"] / f"query{q['query_id']}.csv"
        if csv_file.exists():
            rows_count = _get_csv_rows_cached(csv_file)
                
        # Corrections count from md log (cached)
        corrections = 0
        md_file = DAB_RESULTS_BASE / q["dataset"] / f"query{q['query_id']}.md"
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
def get_dab_queries(date: str = "all"):
    """List all 54 DAB queries with their current status."""
    queries = _get_dab_queries()
    result = []
    for q in queries:
        status_info = _dab_query_status(q["dataset"], q["query_id"], date=date)
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
def get_dab_metrics(date: str = "all", force: bool = False):
    """Get overall DAB accuracy metrics."""
    if force:
        from backend.app.dab.benchmark_loader import load_all_queries
        from backend.app.dab.dab_evaluator import evaluate_answer
        _cached_dab_metrics.cache_clear()
        _DAB_FILE_CACHE.clear()
        cached_dab_dataset_stats.cache_clear()
        
        queries = load_all_queries(DAB_REPO_PATH_DEFAULT)
        for q in queries:
            dataset = q["dataset"]
            qid = str(q["query_id"])
            gt = q["ground_truth"]
            save_dir = DAB_RESULTS_BASE / dataset
            if not save_dir.exists(): continue
            
            val_path = Path(DAB_REPO_PATH_DEFAULT) / f"query_{dataset}" / f"query{qid}" / "validate.py"
            validate_src = val_path.read_text(encoding="utf-8") if val_path.exists() else ""
            
            for ans_file in save_dir.glob(f"query{qid}*_answer.txt"):
                fname = ans_file.stem
                base_part = f"query{qid}"
                if not fname.startswith(base_part): continue
                rest = fname[len(base_part):]
                run_sfx = rest.replace("_answer", "")
                
                eval_path = save_dir / f"query{qid}{run_sfx}_eval.json"
                if not eval_path.exists():
                    agent_ans = ans_file.read_text(encoding="utf-8", errors="ignore").strip()
                    evaluate_answer(dataset, qid, agent_ans, gt, validate_src, save=True, run_suffix=run_sfx)

    return _cached_dab_metrics(date, _get_ttl_hash(5))


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


@router.get("/api/dab/results/{dataset}/{query_id}")
def get_dab_result(dataset: str, query_id: str, date: str = "all"):
    """Get full result details for a specific DAB query."""
    query_id = query_id.lower().replace("query", "")
    from backend.app.dab.dab_evaluator import load_eval_result
    from backend.app.utils.archive import get_target_dirs_for_date

    target_dirs = get_target_dirs_for_date(DAB_RESULTS_BASE, date)
    
    md_file = None
    sql_file = None
    csv_file = None
    answer_file = None
    
    for t_dir in target_dirs:
        if (t_dir / dataset / f"query{query_id}.md").exists():
            result_dir = t_dir / dataset
            md_file = result_dir / f"query{query_id}.md"
            sql_file = result_dir / f"query{query_id}.sql"
            csv_file = result_dir / f"query{query_id}.csv"
            answer_file = result_dir / f"query{query_id}_answer.txt"
            break
            
    if md_file is None:
        result_dir = DAB_RESULTS_BASE / dataset
        md_file = result_dir / f"query{query_id}.md"
        sql_file = result_dir / f"query{query_id}.sql"
        csv_file = result_dir / f"query{query_id}.csv"
        answer_file = result_dir / f"query{query_id}_answer.txt"

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

    eval_result = load_eval_result(dataset, query_id)
    status_info = _dab_query_status(dataset, query_id)

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


@router.post("/api/dab/run/{dataset}/{query_id}")
def run_dab_single(dataset: str, query_id: str):
    """Run a single DAB query through the agent pipeline."""
    query_id = query_id.lower().replace("query", "")
    from backend.app.dab.dab_orchestrator import run_dab_query

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
        from backend.app.services.task_manager import TaskManager
        task_id = TaskManager.start_task('dab_query', qkey)
        try:
            run_dab_query(target)
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
def get_dab_live_log(dataset: str, query_id: str):
    """
    Tail the live log file for a running DAB query.
    Returns parsed milestone steps from the log even while it's being written.
    """
    query_id = query_id.lower().replace("query", "")
    import re as _re

    qkey = f"{dataset}_q{query_id}"
    is_running = qkey in DAB_RUNNING_TASKS

    # Try all possible casing and directory structures for the markdown log file
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
    SSE endpoint â€” pushes log progress to the browser as events happen.
    Replaces client-side polling (was 1.5 s interval, now sub-100 ms latency).
    The browser uses EventSource; each message is a JSON-serialised step list.
    A final 'event: done' frame signals completion so the client can close.
    """
    import re as _re

    qkey = f"{dataset}_q{query_id}"

    def _resolve_md() -> Path | None:
        for p in (
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
            # Honour client disconnect â€” avoids leaking coroutines
            if await request.is_disconnected():
                break

            is_running = qkey in DAB_RUNNING_TASKS
            md_file = _resolve_md()

            if md_file:
                size = md_file.stat().st_size
                if size != last_size:
                    last_size = size
                    try:
                        content = md_file.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        content = ""
                    parsed = _parse_steps(content)
                    # Only push when the step list actually grew â€” no duplicate frames
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


@router.post("/api/dab/stop")
def stop_dab_all():
    """Cancel a running DAB batch job."""
    global DAB_CANCEL_FLAG
    DAB_CANCEL_FLAG = True
    
    # Try to cancel any background tasks managed by TaskManager
    try:
        from backend.app.services.task_manager import TaskManager
        TaskManager.cancel_all()
    except Exception:
        pass
        
    # Clear the running tasks set so the UI instantly stops polling
    DAB_RUNNING_TASKS.clear()
    
    return {"message": "Stop requested. Running queries will finish gracefully."}

@router.delete("/api/dab/runs/{date}")
def delete_dab_run(date: str):
    """Delete a historical run by date or run_id."""
    from datetime import datetime
    from backend.app.utils.archive import force_delete_dir, force_delete_file
    from backend.app.db.database import SessionLocal
    from backend.app.db.models import Evaluation
    from sqlalchemy import cast, Date
    import shutil
    
    if date == "all":
        return {"error": "Cannot delete 'all' dates."}
        
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Delete from Database
    db = SessionLocal()
    try:
        # We need to find records where the casted timestamp matches the date string
        # SQLite dates are strings, so we can use string matching for YYYY-MM-DD
        records_to_delete = db.query(Evaluation).filter(
            Evaluation.timestamp.like(f"{date}%")
        ).all()
        for r in records_to_delete:
            db.delete(r)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to delete Evaluation records for {date}: {e}")
    finally:
        db.close()
    
    # 2. Delete from Filesystem
    if date == today:
        if DAB_RESULTS_DIR.exists():
            for item in DAB_RESULTS_DIR.iterdir():
                if item.name != "_archive":
                    if item.is_dir():
                        force_delete_dir(item)
                    else:
                        force_delete_file(item)
        return {"message": f"Cleared live results for {date}"}
        
    archive_base = DAB_RESULTS_DIR / "_archive"
    if archive_base.exists():
        for run_folder in archive_base.iterdir():
            if run_folder.is_dir():
                try:
                    date_str = run_folder.name.split('_')[1] # YYYYMMDD
                    run_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    if run_date == date:
                        force_delete_dir(run_folder)
                except Exception:
                    pass
    
    _cached_dab_metrics.cache_clear()
    global _dab_queries_cache
    _dab_queries_cache = None
    
    return {"message": f"Run {date} deleted."}


@router.post("/api/dab/run_all")
def run_dab_all(payload: DabRunAllPayload = DabRunAllPayload()):
    """Trigger a full DAB benchmark run (all pending queries)."""
    from backend.app.dab.dab_evaluator import load_eval_result
    import shutil
    from datetime import datetime
    
    global DAB_CANCEL_FLAG
    DAB_CANCEL_FLAG = False

    # Create isolated fresh run folder by archiving current DAB_RESULTS_DIR
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    archive_dir = DAB_RESULTS_DIR / "_archive" / run_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Move all items to archive, except the _archive folder itself
    if DAB_RESULTS_DIR.exists():
        for item in DAB_RESULTS_DIR.iterdir():
            if item.name != "_archive":
                try:
                    shutil.move(str(item), str(archive_dir / item.name))
                except Exception:
                    pass

    # Wipe today's database records to ensure the dashboard resets to 0
    from backend.app.db.models import Evaluation
    from backend.app.db.database import SessionLocal
    db = SessionLocal()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        db.query(Evaluation).filter(Evaluation.timestamp.like(f"{today_str}%")).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to clear today's DB records for fresh run: {e}")
    finally:
        db.close()

    queries = _get_dab_queries()
    if not queries:
        return {"error": "No queries found. Check DAB repo path."}

    to_run = []
    for q in queries:
        if payload.skip_docker and q["needs_docker"]:
            continue
        # Global runs always queue 5 passes for each question
        for i in range(5):
            # We track each run individually. We'll append run_number to instance_id for tracking
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

    def _run_batch():
        from backend.app.dab.dab_orchestrator import run_dab_query
        global DAB_CANCEL_FLAG

        for q in to_run:
            if DAB_CANCEL_FLAG:
                # Discard remaining queued items
                for remaining_q in to_run:
                    DAB_RUNNING_TASKS.discard(remaining_q["instance_id"])
                break
                
            qkey = q["instance_id"]
            try:
                run_dab_query(q, run_number=q.get("run_number", 0))
            except Exception:
                pass
            finally:
                DAB_RUNNING_TASKS.discard(qkey)
        # Invalidate caches
        global _dab_queries_cache
        _dab_queries_cache = None
        _cached_dab_metrics.cache_clear()

    EXECUTION_POOL.submit(_run_batch)
    return {
        "message": f"Started DAB batch run: {len(to_run)} queries queued",
        "count": len(to_run),
        "skip_docker": payload.skip_docker,
    }


@router.get("/api/dab/results/recent")
def get_dab_recent_results(limit: int = 15, date: str = "all"):
    """Return recent DAB eval results formatted like Spider's /api/results/recent."""
    from backend.app.utils.archive import get_target_dirs_for_date
    dab_results_dir = DAB_RESULTS_DIR
    target_dirs = get_target_dirs_for_date(dab_results_dir, date)
    
    eval_files = []
    for t_dir in target_dirs:
        if not t_dir.exists(): continue
        if t_dir == dab_results_dir:
            eval_files.extend([f for f in t_dir.glob("**/*_eval.json") if "_archive" not in [p.name for p in f.parents]])
        else:
            eval_files.extend(list(t_dir.glob("**/*_eval.json")))
    eval_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    recent: List[Dict[str, Any]] = []
    for ef in eval_files[:limit]:
        try:
            with open(ef, "r", encoding="utf-8") as fp:
                ev = json.load(fp)
        except Exception:
            continue

        passed = ev.get("passed", False)
        in_t = ev.get("input_tokens", 0)
        out_t = ev.get("output_tokens", 0)
        total_tokens = in_t + out_t
        
        timestamp = ev.get(
            "timestamp", datetime.fromtimestamp(ef.stat().st_mtime).isoformat()
        )
        
        # Strictly filter by the actual execution timestamp to avoid showing old archived files
        if date != "all" and not timestamp.startswith(date):
            continue

        recent.append(
            {
                "id": ev.get("instance_id", ef.stem.replace("_eval", "")),
                "db": ev.get("dataset", ef.parent.name),
                "status": "success" if passed else "error",
                "gold_status": "gold_pass" if passed else "gold_fail",
                "latency": round(ev.get("elapsed_s", 0), 1),
                "complexity": "medium",
                "complexity_type": "Unclassified",
                "complexity_score": 0.0,
                "corrections": 0,
                "critic_rounds": 0,
                "rows": 0,
                "timestamp": timestamp,
                "total_tokens": total_tokens,
                "cost": round(total_tokens * 0.000003, 6),
                "reason": ev.get("reason", ""),
            }
        )
        if len(recent) >= limit:
            break
            
    return recent


@router.get("/api/dab/status")
def get_dab_run_status():
    """Get which DAB queries are currently running from DB."""
    from backend.app.services.task_manager import TaskManager
    running_tasks = TaskManager.get_running_tasks()
    
    # Also check the old memory-based set just in case some tasks didn't migrate
    all_running = list(DAB_RUNNING_TASKS) + [t["target"] for t in running_tasks]
    
    # Calculate global completion progress for the active batch
    # 54 canonical queries * 5 runs = 270 total
    queries = _get_dab_queries()
    total_queries = len(queries) * 5
    
    # Calculate how many of the 5 runs are complete for each query
    completed_queries = 0
    from backend.app.core.config import DAB_RESULTS_DIR
    
    try:
        # Instead of hitting SQLite which locks, just count the raw JSON results directly
        if DAB_RESULTS_DIR.exists():
            completed_queries = len([f for f in DAB_RESULTS_DIR.rglob("*_eval.json") if "_archive" not in f.parts])
    except Exception:
        pass
    
    return {
        "running": all_running,
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
    from backend.app.core.config import DAB_REPO as DAB_REPO_PATH

    def _run():
        try:
            from backend.app.core.rules.self_improving_loop import SelfImprovingLoop

            loop = SelfImprovingLoop(dab_repo=str(DAB_REPO_PATH))
            loop.run_daily()
        except Exception as e:
            import traceback as tb

            logger.error(f"Improvement run failed: {e}\n{tb.format_exc()}")

    background_tasks.add_task(_run)
    return {
        "message": "Self-improvement run started in background. Check /api/improvement/status for results."
    }


# ---------------------------------------------------------------------------
# LangSmith Evaluators API
# ---------------------------------------------------------------------------

DAB_RESULTS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "results" / "dab"
)

_langsmith_eval_running = False


@router.get("/api/langsmith/status")
async def langsmith_status():
    """
    Return LangSmith connection status, project info, and dataset stats.
    Also shows per-evaluator aggregate scores from stored DAB eval results.
    """
    from backend.app.core.langsmith_evaluators import (
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
            from backend.app.core.langsmith_evaluators import build_dab_dataset

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
            from backend.app.core.langsmith_evaluators import run_langsmith_experiment

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
async def get_langsmith_scores():
    """
    Return per-query evaluator scores from stored DAB eval JSON records.
    Used by the UI to show the evaluator scorecard.
    """
    rows = []
    if not DAB_RESULTS_PATH.exists():
        return {"scores": rows}

    from backend.app.core.langsmith_evaluators import run_all_evaluators

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





@router.delete("/api/dab/runs/{date}")
def delete_dab_run(date: str):
    """Delete a historical DAB run by date from DB and filesystem."""
    from backend.app.db.database import SessionLocal
    from backend.app.db.models import Evaluation
    from backend.app.utils.archive import force_delete_dir, force_delete_file
    
    if date == "all":
        return {"error": "Cannot delete 'all' dates."}
        
    db = SessionLocal()
    try:
        db.query(Evaluation).filter(Evaluation.timestamp.like(f"{date}%")).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"Failed to delete records: {e}"}
    finally:
        db.close()
        
    today = datetime.now().strftime("%Y-%m-%d")
    
    if date == today:
        if DAB_RESULTS_BASE.exists():
            for item in DAB_RESULTS_BASE.iterdir():
                if item.name != "_archive":
                    if item.is_dir():
                        force_delete_dir(item)
                    else:
                        force_delete_file(item)
        return {"message": f"Cleared live DAB results for {date}"}
        
    archive_base = DAB_RESULTS_BASE / "_archive"
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
                    
    return {"message": f"Deleted historical DAB run for {date}"}

# Telemetry monitor endpoint removed as PipelineMonitor is deprecated.


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)

