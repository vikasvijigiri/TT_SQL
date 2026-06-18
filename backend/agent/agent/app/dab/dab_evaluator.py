"""
dab_evaluator.py
----------------
Evaluates agent answers against DataAgentBench ground truth using each
query's validate.py logic. Two evaluation modes:

  1. Dynamic (preferred): Executes the actual validate.py from the query folder.
  2. Static fallback: Checks if ground_truth string appears in the agent answer.

Results stored as: backend/results/dab/{dataset}/query{id}_eval.json
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from agent.app.core.config import DAB_REPO, RESULTS_DIR
import contextlib

from agent.app.core.config import DAB_RESULTS_DIR, DEFAULT_USERNAME
from agent.app.db.database import SessionLocal
from agent.app.db.models import Evaluation
from sqlalchemy import cast, Date

DAB_RUN_DATE: Optional[str] = None
DAB_RUN_ID: Optional[str] = None
DAB_RUN_USERNAME: Optional[str] = None  # set by run_all to scope results per user


def _validation_worker(validate_src: str, agent_answer: str, filepath: str | None, return_dict: dict):
    import sys
    from agent.app.core.config import DAB_REPO
    dab_path = str(DAB_REPO)
    if dab_path not in sys.path:
        sys.path.insert(0, dab_path)
    try:
        namespace = {}
        if filepath:
            namespace["__file__"] = filepath
        exec(compile(validate_src, filepath or "<validate>", "exec"), namespace)
        validate_fn = namespace.get("validate")
        if callable(validate_fn):
            result = validate_fn(agent_answer)
            if isinstance(result, tuple) and len(result) == 2:
                return_dict["passed"] = bool(result[0])
                return_dict["reason"] = str(result[1])
            else:
                return_dict["passed"] = bool(result)
                return_dict["reason"] = "OK" if result else "FAIL"
        else:
            return_dict["passed"] = False
            return_dict["reason"] = "No validate_fn found"
    except Exception as e:
        return_dict["passed"] = False
        return_dict["reason"] = f"Exception: {str(e)}"

def _run_dynamic_validate(
    validate_src: str, agent_answer: str, filepath: str | None = None
) -> Tuple[bool, str]:
    """
    Execute the validate.py source in an isolated child process to forcefully 
    prevent LLM-generated SQL from crashing/hanging the host machine.
    """
    import multiprocessing
    
    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    # Default state if process is killed or fails
    return_dict["passed"] = False
    return_dict["reason"] = "Timeout Error: Query execution exceeded 30 seconds (KILLED)."
    
    p = multiprocessing.Process(
        target=_validation_worker,
        args=(validate_src, agent_answer, filepath, return_dict)
    )
    p.start()
    p.join(timeout=30)
    
    if p.is_alive():
        p.terminate()
        p.join()
        
    return return_dict["passed"], return_dict["reason"]


def _run_static_validate(ground_truth: str, agent_answer: str) -> Tuple[bool, str]:
    """
    Fallback: check if ground_truth string appears in agent_answer (case-insensitive).
    """
    if not ground_truth:
        return False, "No ground truth available"
    gt = ground_truth.strip().lower()
    ans = agent_answer.strip().lower()
    if gt in ans:
        return True, f"Ground truth '{ground_truth}' found in answer"
    return False, f"Ground truth '{ground_truth}' NOT found in answer"


def evaluate_answer(
    dataset: str,
    query_id: str,
    agent_answer: str,
    ground_truth: str,
    validate_src: str,
    save: bool = True,
    elapsed_s: Optional[float] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    run_suffix: str = "",
) -> Dict[str, Any]:
    """
    Grade a single DAB answer.

    Args:
        dataset: e.g. "bookreview"
        query_id: e.g. "1"
        agent_answer: The text produced by the agent (includes SQL and natural language)
        ground_truth: Expected answer string from ground_truth.csv
        validate_src: Source code of validate.py
        save: If True, persist result to disk

    Returns:
        dict with: passed, reason, method, timestamp
    """
    # Try dynamic validation first
    if validate_src:
        validate_py_path = str(
            DAB_REPO / f"query_{dataset}" / f"query{query_id}" / "validate.py"
        )
        passed, reason = _run_dynamic_validate(
            validate_src, agent_answer, filepath=validate_py_path
        )
        method = "dynamic_validate_py"
    else:
        passed, reason = _run_static_validate(ground_truth, agent_answer)
        method = "static_contains_check"

    now_time = datetime.now()
    if DAB_RUN_DATE:
        try:
            target_d = datetime.strptime(DAB_RUN_DATE, "%Y-%m-%d")
            now_time = now_time.replace(year=target_d.year, month=target_d.month, day=target_d.day)
        except Exception:
            pass

    result = {
        "dataset": dataset,
        "query_id": query_id,
        "instance_id": f"{dataset}_q{query_id}",
        "passed": passed,
        "reason": reason,
        "method": method,
        "ground_truth": ground_truth,
        "agent_answer_snippet": agent_answer[:500] if agent_answer else "",
        "elapsed_s": elapsed_s,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "timestamp": now_time.isoformat(),
    }

    if save:
        db = SessionLocal()
        try:
            ts_str = result.get("timestamp")
            eval_record = Evaluation(
                dataset=dataset,
                query_id=query_id,
                instance_id=f"{dataset}_q{query_id}",
                run_suffix=run_suffix,
                passed=passed,
                reason=reason,
                method=method,
                ground_truth=ground_truth,
                agent_answer_snippet=agent_answer[:500] if agent_answer else "",
                elapsed_s=elapsed_s,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                timestamp=datetime.fromisoformat(ts_str) if ts_str else datetime.utcnow(),
                run_id=DAB_RUN_ID or "live",
                username=DAB_RUN_USERNAME or DEFAULT_USERNAME
            )
            db.add(eval_record)
            db.commit()
        except Exception as e:
            print(f"Failed to save evaluation to DB: {e}")
        finally:
            db.close()

    return result


def load_eval_result(
    dataset: str, query_id: str, run_suffix: str = "", date: str = "all", run_id: Optional[str] = None,
    username: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Load a previously saved evaluation result from the database, optionally scoped by username."""
    db = SessionLocal()
    try:
        query = db.query(Evaluation).filter(
            Evaluation.dataset == dataset,
            Evaluation.query_id == str(query_id),
            Evaluation.run_suffix == run_suffix
        )
        
        # Filter by username when provided (isolates user data)
        if username:
            query = query.filter(Evaluation.username == username)

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
            query = query.filter(Evaluation.timestamp >= start_dt, Evaluation.timestamp < end_dt)
            
        record = query.order_by(Evaluation.timestamp.desc()).first()
        
        if not record:
            return None
            
        return {
            "dataset": record.dataset,
            "query_id": record.query_id,
            "instance_id": record.instance_id,
            "passed": record.passed,
            "reason": record.reason,
            "method": record.method,
            "ground_truth": record.ground_truth,
            "agent_answer_snippet": record.agent_answer_snippet,
            "elapsed_s": record.elapsed_s,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "timestamp": record.timestamp.isoformat() if record.timestamp else ""
        }
    except Exception as e:
        print(f"Failed to load eval result from DB: {e}")
        return None
    finally:
        db.close()


def load_agent_answer(dataset: str, query_id: str) -> Optional[str]:
    """Load agent's raw answer text from the results directory."""
    result_dir = DAB_RESULTS_DIR / dataset
    # Try answer file first
    answer_file = result_dir / f"query{query_id}_answer.txt"
    if answer_file.exists():
        return answer_file.read_text(encoding="utf-8").strip()

    # Try markdown log
    md_file = result_dir / f"query{query_id}.md"
    if md_file.exists():
        content = md_file.read_text(encoding="utf-8", errors="replace")
        # Extract the final answer section if present
        match = re.search(
            r"## FINAL ANSWER[:\s]*(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return content[:2000]  # Fallback: first 2000 chars of log
    return None


def compute_accuracy(
    queries: List[Dict[str, Any]], max_runs: int = 5, date: str = "all", run_id: Optional[str] = None,
    username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute Pass@1 and Pass@K accuracy across all evaluated queries.

    Definitions (matching the DAB benchmark standard):
      pass@1 = (total passing run-slots) / (total run-slots evaluated)
               i.e. the run-level success rate averaged over ALL independent runs.
               Example: bookreview 3 queries x 5 runs = 15 slots; if 14 pass -> 93.3%

      pass@K = (queries where ANY of the K runs passed) / (queries evaluated)
               i.e. query-level: did the system get it right at least once?

    K is auto-detected from how many _run{n}_eval.json files exist on disk.
    A query is "pending" if run-0 eval file does not exist yet.

    Args:
        queries: List of query dicts from benchmark_loader.load_all_queries()
        max_runs: Upper bound for scanning _run{n} files (default 5).
        date: Optional YYYY-MM-DD string to filter results by execution day.
    """
    total_queries = 0
    pending = 0

    # Run-level tallies (for pass@1 = slot-level success rate)
    total_run_slots = 0
    passing_run_slots = 0

    # Query-level tallies (for pass@K)
    queries_with_any_pass = 0

    per_dataset: Dict[str, Dict] = {}

    for q in queries:
        dataset = q["dataset"]
        qid = q["query_id"]

        if dataset not in per_dataset:
            per_dataset[dataset] = {
                "total": 0,  # queries
                "pending": 0,
                "evaluated": 0,
                "run_slots": 0,  # total run slots (queries x K)
                "passing_slots": 0,  # slots that passed
                "passed_atk": 0,  # queries with any passing run
                "queries": [],
            }

        per_dataset[dataset]["total"] += 1
        total_queries += 1

        # Collect any completed runs (0 to max_runs-1) for today
        run_results = []
        for r in range(max_runs):
            sfx = "" if r == 0 else f"_run{r}"
            rv = load_eval_result(dataset, qid, run_suffix=sfx, date=date, run_id=run_id, username=username)
            if rv is not None:
                if run_id is None and date != "all":
                    file_date = rv.get("timestamp", "")[:10]
                    if file_date != date:
                        continue
                run_results.append(rv)

        if not run_results:
            per_dataset[dataset]["pending"] += 1
            pending += 1
            per_dataset[dataset]["queries"].append(
                {
                    "query_id": qid,
                    "status": "pending",
                    "passed": None,
                }
            )
            continue

        run0 = run_results[0]
        k = len(run_results)
        passing = sum(1 for rv in run_results if rv.get("passed", False))
        any_pass = passing > 0

        # Run-level tallies
        total_run_slots += k
        passing_run_slots += passing
        per_dataset[dataset]["run_slots"] += k
        per_dataset[dataset]["passing_slots"] += passing
        per_dataset[dataset]["evaluated"] += 1

        if any_pass:
            queries_with_any_pass += 1
            per_dataset[dataset]["passed_atk"] += 1

        # Per-run breakdown for reporting
        runs_detail = [
            {
                "run": i,
                "passed": bool(rv.get("passed", False)),
                "reason": (rv.get("reason") or "")[:120],
            }
            for i, rv in enumerate(run_results)
        ]

        per_dataset[dataset]["queries"].append(
            {
                "query_id": qid,
                "status": "evaluated",
                "num_runs": k,
                "passing_runs": passing,
                "passed_atk": any_pass,
                "runs": runs_detail,
                "reason": run0.get("reason", ""),
                "elapsed_s": run0.get("elapsed_s"),
                "input_tokens": run0.get("input_tokens"),
                "output_tokens": run0.get("output_tokens"),
            }
        )

    evaluated_queries = total_queries - pending

    # Global K = max runs seen across any evaluated query
    global_k = max(
        (
            len(q.get("runs") or [])
            for ds in per_dataset.values()
            for q in ds["queries"]
            if q.get("runs")
        ),
        default=1,
    )

    # pass@1 = run-slot success rate (Claude's definition)
    pass_at_1 = (passing_run_slots / total_run_slots) if total_run_slots > 0 else 0.0
    # pass@K = query-level any-run success rate
    pass_at_k = (
        (queries_with_any_pass / evaluated_queries) if evaluated_queries > 0 else 0.0
    )

    # Per-dataset pass@1 and pass@K
    for ds_info in per_dataset.values():
        slots = ds_info["run_slots"]
        passing_s = ds_info["passing_slots"]
        evaled = ds_info["evaluated"]
        atk = ds_info["passed_atk"]
        ds_info["pass_at_1"] = round(passing_s / slots, 4) if slots > 0 else 0.0
        ds_info["pass_at_1_pct"] = (
            f"{passing_s / slots * 100:.1f}%" if slots > 0 else "N/A"
        )
        ds_info["pass_at_k"] = round(atk / evaled, 4) if evaled > 0 else 0.0
        ds_info["pass_at_k_pct"] = f"{atk / evaled * 100:.1f}%" if evaled > 0 else "N/A"

    total_time = sum(
        q.get("elapsed_s")
        for ds in per_dataset.values()
        for q in ds["queries"]
        if q.get("elapsed_s") is not None
    )
    total_input_tokens = sum(
        q.get("input_tokens")
        for ds in per_dataset.values()
        for q in ds["queries"]
        if q.get("input_tokens") is not None
    )
    total_output_tokens = sum(
        q.get("output_tokens")
        for ds in per_dataset.values()
        for q in ds["queries"]
        if q.get("output_tokens") is not None
    )

    return {
        "total_queries": total_queries,
        "evaluated": evaluated_queries,
        "pending": pending,
        "total_run_slots": total_run_slots,
        "passing_run_slots": passing_run_slots,
        "queries_passed_atk": queries_with_any_pass,
        "num_runs": global_k,
        "pass_at_1": round(pass_at_1, 4),
        "pass_at_1_pct": f"{pass_at_1 * 100:.1f}%",
        "pass_at_k": round(pass_at_k, 4),
        "pass_at_k_pct": f"{pass_at_k * 100:.1f}%",
        "total_elapsed_time_s": round(total_time, 2),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "per_dataset": per_dataset,
        "computed_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from agent.app.dab.benchmark_loader import load_all_queries

    dab_repo = str(DAB_REPO)
    queries = load_all_queries(dab_repo)
    metrics = compute_accuracy(queries)
    print(json.dumps(metrics, indent=2))


# ── Multi-Process Shared State sync via cache_service (Redis) ──
import sys

class _DABModuleWrapper(object):
    def __init__(self, wrapped):
        self.__dict__["_wrapped"] = wrapped

    def __getattr__(self, name):
        if name in ("DAB_RUN_ID", "DAB_RUN_DATE", "DAB_RUN_USERNAME"):
            try:
                from agent.app.utils.cache import cache_service
                return cache_service.get(f"shared_{name}")
            except Exception:
                return getattr(self._wrapped, name)
        return getattr(self._wrapped, name)

    def __setattr__(self, name, value):
        if name in ("DAB_RUN_ID", "DAB_RUN_DATE", "DAB_RUN_USERNAME"):
            try:
                from agent.app.utils.cache import cache_service
                cache_service.set(f"shared_{name}", value, ttl=86400)
            except Exception:
                pass
            try:
                setattr(self._wrapped, name, value)
            except Exception:
                pass
        else:
            setattr(self._wrapped, name, value)

sys.modules[__name__] = _DABModuleWrapper(sys.modules[__name__])
