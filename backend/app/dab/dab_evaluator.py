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
import types
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from backend.app.core.config import DAB_REPO

DAB_RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results" / "dab"


def _run_dynamic_validate(validate_src: str, agent_answer: str, filepath: str = None) -> Tuple[bool, str]:
    """
    Execute the validate.py source in a sandboxed namespace and call validate(agent_answer).
    Returns (passed: bool, reason: str).
    """
    import sys
    dab_path = str(DAB_REPO)
    added_to_path = False
    if dab_path not in sys.path:
        sys.path.insert(0, dab_path)
        added_to_path = True
    try:
        namespace = {}
        if filepath:
            namespace["__file__"] = filepath
        exec(compile(validate_src, filepath or "<validate>", "exec"), namespace)
        validate_fn = namespace.get("validate")
        if callable(validate_fn):
            result = validate_fn(agent_answer)
            if isinstance(result, tuple) and len(result) == 2:
                passed, reason = result
                return bool(passed), str(reason)
            return bool(result), "OK" if result else "FAIL"
    except Exception as e:
        return False, f"validate.py execution error: {e}"
    finally:
        if added_to_path and dab_path in sys.path:
            try:
                sys.path.remove(dab_path)
            except ValueError:
                pass
    return False, "No validate() function found"


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
        passed, reason = _run_dynamic_validate(validate_src, agent_answer, filepath=validate_py_path)
        method = "dynamic_validate_py"
    else:
        passed, reason = _run_static_validate(ground_truth, agent_answer)
        method = "static_contains_check"

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
        "timestamp": datetime.now().isoformat(),
    }

    if save:
        save_dir = DAB_RESULTS_DIR / dataset
        save_dir.mkdir(parents=True, exist_ok=True)
        eval_path = save_dir / f"query{query_id}{run_suffix}_eval.json"
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


def load_eval_result(dataset: str, query_id: str, run_suffix: str = "") -> Optional[Dict[str, Any]]:
    """Load a previously saved evaluation result."""
    eval_path = DAB_RESULTS_DIR / dataset / f"query{query_id}{run_suffix}_eval.json"
    if not eval_path.exists():
        return None
    try:
        with open(eval_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


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
        match = re.search(r"## FINAL ANSWER[:\s]*(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return content[:2000]  # Fallback: first 2000 chars of log
    return None


def compute_accuracy(queries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute Pass@1 accuracy across all evaluated queries.
    
    Args:
        queries: List of query dicts from benchmark_loader.load_all_queries()
        
    Returns:
        Overall and per-dataset accuracy metrics
    """
    total = 0
    passed_total = 0
    pending = 0
    per_dataset: Dict[str, Dict] = {}

    for q in queries:
        dataset = q["dataset"]
        qid = q["query_id"]

        if dataset not in per_dataset:
            per_dataset[dataset] = {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "pending": 0,
                "queries": [],
            }

        eval_result = load_eval_result(dataset, qid)
        per_dataset[dataset]["total"] += 1
        total += 1

        if eval_result is None:
            per_dataset[dataset]["pending"] += 1
            pending += 1
            per_dataset[dataset]["queries"].append({
                "query_id": qid,
                "status": "pending",
                "passed": None,
            })
        else:
            p = eval_result.get("passed", False)
            if p:
                per_dataset[dataset]["passed"] += 1
                passed_total += 1
            else:
                per_dataset[dataset]["failed"] += 1
            per_dataset[dataset]["queries"].append({
                "query_id": qid,
                "status": "evaluated",
                "passed": p,
                "reason": eval_result.get("reason", ""),
                "elapsed_s": eval_result.get("elapsed_s"),
                "input_tokens": eval_result.get("input_tokens"),
                "output_tokens": eval_result.get("output_tokens"),
            })

    evaluated = total - pending
    accuracy = (passed_total / evaluated) if evaluated > 0 else 0.0

    total_time = sum(q.get("elapsed_s") for ds in per_dataset.values() for q in ds["queries"] if q.get("elapsed_s") is not None)
    total_input_tokens = sum(q.get("input_tokens") for ds in per_dataset.values() for q in ds["queries"] if q.get("input_tokens") is not None)
    total_output_tokens = sum(q.get("output_tokens") for ds in per_dataset.values() for q in ds["queries"] if q.get("output_tokens") is not None)

    return {
        "total_queries": total,
        "evaluated": evaluated,
        "pending": pending,
        "passed": passed_total,
        "failed": evaluated - passed_total,
        "pass_at_1": round(accuracy, 4),
        "pass_at_1_pct": f"{accuracy * 100:.1f}%",
        "total_elapsed_time_s": round(total_time, 2),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "per_dataset": per_dataset,
        "computed_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from backend.app.dab.benchmark_loader import load_all_queries

    dab_repo = str(DAB_REPO)
    queries = load_all_queries(dab_repo)
    metrics = compute_accuracy(queries)
    print(json.dumps(metrics, indent=2))
