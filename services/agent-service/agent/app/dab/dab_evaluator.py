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

from agent.app.core.config import DAB_REPO, DAB_RESULTS_DIR, DEFAULT_USERNAME
from agent.app.db.database import SessionLocal
from agent.app.db.models import Evaluation

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
    Execute the validate.py source in an isolated thread with a 30-second timeout.
    Uses threading instead of multiprocessing so it works safely from any thread
    on Windows (multiprocessing.Process can only be spawned from the main thread).
    """
    import threading

    return_dict: dict = {
        "passed": False,
        "reason": "Timeout Error: Query execution exceeded 30 seconds (KILLED).",
    }

    t = threading.Thread(
        target=_validation_worker,
        args=(validate_src, agent_answer, filepath, return_dict),
        daemon=True,
    )
    t.start()
    t.join(timeout=30)
    # If still alive the daemon thread will be abandoned; we return the timeout default.
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

    import sys
    wrapper = sys.modules[__name__]
    
    now_time = datetime.now()
    if wrapper.DAB_RUN_DATE:
        try:
            target_d = datetime.strptime(wrapper.DAB_RUN_DATE, "%Y-%m-%d")
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
                run_id=wrapper.DAB_RUN_ID or "live",
                username=wrapper.DAB_RUN_USERNAME or DEFAULT_USERNAME
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


def load_all_eval_results(
    dataset: str, query_id: str, date: str = "all", run_id: Optional[str] = None,
    username: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Return the latest eval result for EVERY run-slot of a query (all run_suffixes),
    sorted by run number ascending. No upper bound on number of runs.
    """
    from datetime import timedelta
    db = SessionLocal()
    try:
        q = db.query(Evaluation).filter(
            Evaluation.dataset == dataset,
            Evaluation.query_id == str(query_id),
        )
        if username:
            q = q.filter(Evaluation.username == username)
        if run_id is not None:
            if run_id == "live":
                q = q.filter((Evaluation.run_id == "live") | (Evaluation.run_id == None))
            elif run_id != "all":
                q = q.filter(Evaluation.run_id == run_id)
        elif date != "all":
            start_dt = datetime.strptime(date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=1)
            q = q.filter(Evaluation.timestamp >= start_dt, Evaluation.timestamp < end_dt)

        records = q.order_by(Evaluation.timestamp.desc()).all()

        # Keep only the latest record per run_suffix (in case a slot was retried)
        seen: Dict[str, Any] = {}
        for rec in records:
            sfx = rec.run_suffix or ""
            if sfx not in seen:
                seen[sfx] = rec

        def _run_order(sfx: str) -> int:
            if sfx == "":
                return 0
            m = re.match(r"_run(\d+)$", sfx)
            return int(m.group(1)) if m else 999

        return [
            {
                "dataset": rec.dataset,
                "query_id": rec.query_id,
                "passed": rec.passed,
                "reason": rec.reason,
                "elapsed_s": rec.elapsed_s,
                "input_tokens": rec.input_tokens,
                "output_tokens": rec.output_tokens,
                "timestamp": rec.timestamp.isoformat() if rec.timestamp else "",
            }
            for rec in sorted(seen.values(), key=lambda r: _run_order(r.run_suffix or ""))
        ]
    except Exception as e:
        print(f"Failed to load all eval results for {dataset} q{query_id}: {e}")
        return []
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


def _pass_at_k_unbiased(n: int, c: int, k: int) -> float:
    """
    Official DAB unbiased pass@k estimator (from common_scaffold/validate/pass_k.py).
      pass@k = 1 - C(n-c, k) / C(n, k)
    For k=1 this equals c/n.  For k>=n it equals 1 if c>0 else 0.
    """
    from math import comb
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def compute_accuracy(
    queries: List[Dict[str, Any]], date: str = "all", run_id: Optional[str] = None,
    username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute Pass@1 and Pass@K accuracy matching the official DAB benchmark standard.

    Official methodology (common_scaffold/validate/pass_k.py + stats_scripts/):
      pass@1 per query  = pass_at_k_unbiased(n, c, k=1) = c/n
      pass@1 per dataset = mean(per-query pass@1 values)
      pass@1 leaderboard = mean across all datasets  ← equal weight per dataset

      pass@K per query  = pass_at_k_unbiased(n, c, k=n) = 1 if c>0 else 0
      pass@K leaderboard = mean across all datasets of (fraction of queries with any pass)

    Aggregation is per-dataset-then-mean, NOT a flat slot ratio.  crmarenapro's 13
    queries do not outweigh bookreview's 2 queries on the leaderboard.

    K is auto-detected from the database — no upper-bound cap on number of runs.
    A query is "pending" if it has no eval records at all.
    """
    total_queries = 0
    pending = 0

    # Run-slot tallies (for pass@1)
    total_run_slots = 0
    passing_run_slots = 0

    # Query-level tallies (for pass@K)
    queries_with_any_pass = 0

    # Aggregate resource usage across ALL run slots
    total_elapsed_s = 0.0
    total_input_tokens = 0
    total_output_tokens = 0

    per_dataset: Dict[str, Dict] = {}

    for q in queries:
        dataset = q["dataset"]
        qid = q["query_id"]

        if dataset not in per_dataset:
            per_dataset[dataset] = {
                "total": 0,
                "pending": 0,
                "evaluated": 0,
                "run_slots": 0,
                "passing_slots": 0,
                "passed_atk": 0,
                "queries": [],
            }

        per_dataset[dataset]["total"] += 1
        total_queries += 1

        # One DB call returns all run-slots for this query (no fixed cap)
        run_results = load_all_eval_results(dataset, qid, date=date, run_id=run_id, username=username)

        if not run_results:
            per_dataset[dataset]["pending"] += 1
            pending += 1
            per_dataset[dataset]["queries"].append({"query_id": qid, "status": "pending", "passed": None})
            continue

        k = len(run_results)
        passing = sum(1 for rv in run_results if rv.get("passed", False))
        any_pass = passing > 0

        # Run-slot tallies
        total_run_slots += k
        passing_run_slots += passing
        per_dataset[dataset]["run_slots"] += k
        per_dataset[dataset]["passing_slots"] += passing
        per_dataset[dataset]["evaluated"] += 1

        if any_pass:
            queries_with_any_pass += 1
            per_dataset[dataset]["passed_atk"] += 1

        # Aggregate resource usage over ALL runs for this query
        q_elapsed = sum(rv.get("elapsed_s") or 0.0 for rv in run_results)
        q_input   = sum(rv.get("input_tokens") or 0 for rv in run_results)
        q_output  = sum(rv.get("output_tokens") or 0 for rv in run_results)
        total_elapsed_s      += q_elapsed
        total_input_tokens   += q_input
        total_output_tokens  += q_output

        runs_detail = [
            {"run": i, "passed": bool(rv.get("passed", False)), "reason": (rv.get("reason") or "")[:120]}
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
                "reason": run_results[0].get("reason", ""),
                # totals across all runs (used by the resource-usage aggregation above)
                "elapsed_s": q_elapsed,
                "input_tokens": q_input,
                "output_tokens": q_output,
            }
        )

    evaluated_queries = total_queries - pending

    # Actual K = max run-slots seen across any evaluated query
    global_k = max(
        (len(q.get("runs") or []) for ds in per_dataset.values() for q in ds["queries"] if q.get("runs")),
        default=0,
    )

    # ── Per-dataset stats (per-query pass@1 averaged within the dataset) ─────
    for ds_info in per_dataset.values():
        slots  = ds_info["run_slots"]
        pass_s = ds_info["passing_slots"]
        evaled = ds_info["evaluated"]
        atk    = ds_info["passed_atk"]
        # pass@1 per dataset = mean(c_q / n_q) for each query; since all n_q are equal
        # this equals passing_slots / run_slots — same formula, same result.
        ds_info["pass_at_1"]     = round(pass_s / slots, 4) if slots > 0 else 0.0
        ds_info["pass_at_1_pct"] = f"{pass_s / slots * 100:.1f}%" if slots > 0 else "N/A"
        ds_info["pass_at_k"]     = round(atk / evaled, 4) if evaled > 0 else 0.0
        ds_info["pass_at_k_pct"] = f"{atk / evaled * 100:.1f}%" if evaled > 0 else "N/A"

    # ── Leaderboard metrics: mean across datasets (official DAB aggregation) ──
    # Each dataset contributes equally regardless of how many queries it has.
    ds_with_evals = [info for info in per_dataset.values() if info["evaluated"] > 0]
    if ds_with_evals:
        pass_at_1 = sum(info["pass_at_1"] for info in ds_with_evals) / len(ds_with_evals)
        pass_at_k = sum(info["pass_at_k"] for info in ds_with_evals) / len(ds_with_evals)
    else:
        pass_at_1 = 0.0
        pass_at_k = 0.0

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
        # Raw slot counts kept for reference (not used for leaderboard ranking)
        "raw_pass_at_1_slot_ratio": round(passing_run_slots / total_run_slots, 4) if total_run_slots else 0.0,
        "total_elapsed_time_s": round(total_elapsed_s, 2),
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
