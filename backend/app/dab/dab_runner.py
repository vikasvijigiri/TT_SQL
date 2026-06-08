"""
dab_runner.py
-------------
Batch runner for all 54 DataAgentBench queries.

Usage:
    python backend/app/dab/dab_runner.py --all
    python backend/app/dab/dab_runner.py --dataset bookreview
    python backend/app/dab/dab_runner.py --dataset bookreview --query_id 1
    python backend/app/dab/dab_runner.py --skip_docker   # Only SQLite + DuckDB datasets
"""

import sys
import json
import time
import argparse
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.dab.benchmark_loader import load_all_queries, summarize_queries
from backend.app.dab.dab_orchestrator import run_dab_query, DAB_RESULTS_DIR
from backend.app.dab.dab_evaluator import compute_accuracy, load_eval_result
from backend.app.utils.llm import LLMClient
from backend.app.core.config import DAB_REPO

DAB_REPO_DEFAULT = str(DAB_REPO)


def print_progress_bar(current: int, total: int, prefix: str = "", width: int = 40) -> None:
    filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = 100 * current / total if total > 0 else 0
    print(f"\r{prefix} [{bar}] {current}/{total} ({pct:.0f}%)", end="", flush=True)


def run_all(
    queries: List[Dict[str, Any]],
    workers: int = 1,
    skip_docker: bool = False,
    dataset_filter: Optional[str] = None,
    query_id_filter: Optional[str] = None,
    force_rerun: bool = False,
) -> List[Dict[str, Any]]:
    """Run all (or filtered) queries and return results."""
    
    # Apply filters
    filtered = queries
    if skip_docker:
        filtered = [q for q in filtered if not q["needs_docker"]]
        print(f"[skip_docker] Filtered to {len(filtered)} queries (SQLite + DuckDB only)")
    if dataset_filter:
        filtered = [q for q in filtered if q["dataset"].lower() == dataset_filter.lower()]
    if query_id_filter:
        filtered = [q for q in filtered if q["query_id"] == str(query_id_filter)]

    # Skip already-evaluated queries unless force_rerun
    if not force_rerun:
        pending = []
        for q in filtered:
            ev = load_eval_result(q["dataset"], q["query_id"])
            if ev is None:
                pending.append(q)
            else:
                print(f"  [SKIP] {q['instance_id']} (already evaluated: {'PASS' if ev.get('passed') else 'FAIL'})")
        filtered = pending

    if not filtered:
        print("\n[OK] All queries already evaluated. Use --force to re-run.")
        return []

    print(f"\n[RUN] Running {len(filtered)} queries  (workers={workers})")
    print("-" * 60)

    results = []
    passed = 0
    failed = 0
    errors = 0

    llm_client = LLMClient()

    if workers == 1:
        for i, q in enumerate(filtered, 1):
            print(f"\n[{i}/{len(filtered)}] {q['instance_id']}")
            print_progress_bar(i - 1, len(filtered), prefix="Progress")
            result = run_dab_query(q, llm_client=llm_client)
            results.append(result)
            if result["status"] == "passed":
                passed += 1
                print(f"\n  [PASS] {result['reason'][:80]}")
            elif result["status"] == "error":
                errors += 1
                print(f"\n  [ERROR] {result['error'][:80]}")
            else:
                failed += 1
                print(f"\n  [FAIL] {result['reason'][:80]}")
            # Update and save the summary report on the fly
            print_summary(results, queries)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(run_dab_query, q, llm_client): q for q in filtered}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                print_progress_bar(completed, len(filtered), prefix="Progress")
                try:
                    result = future.result()
                    results.append(result)
                    if result["status"] == "passed":
                        passed += 1
                    elif result["status"] == "error":
                        errors += 1
                    else:
                        failed += 1
                except Exception as e:
                    errors += 1
                    q = futures[future]
                    results.append({
                        "dataset": q["dataset"],
                        "query_id": q["query_id"],
                        "status": "error",
                        "passed": False,
                        "error": str(e),
                    })
                # Update and save the summary report on the fly
                print_summary(results, queries)

    print("\n")
    return results


def print_summary(results: List[Dict[str, Any]], all_queries: List[Dict[str, Any]]) -> None:
    """Print a formatted summary with accuracy."""
    accuracy = compute_accuracy(all_queries)

    print("\n" + "=" * 68)
    print("  DAB BENCHMARK RESULTS — SpiderDIN / TT_SQL_V2")
    print("=" * 68)
    print(f"  Total Queries  : {accuracy['total_queries']}")
    print(f"  Evaluated      : {accuracy['evaluated']}")
    print(f"  Pending        : {accuracy['pending']}")
    print(f"  Passed         : {accuracy['passed']}")
    print(f"  Failed         : {accuracy['failed']}")
    print(f"  Pass@1         : {accuracy['pass_at_1_pct']}")
    print("-" * 68)
    print(f"  {'Dataset':<24} {'Total':>5} {'Pass':>5} {'Fail':>5} {'Pend':>5} {'Acc':>7}")
    print("-" * 68)
    for ds, stats in sorted(accuracy["per_dataset"].items()):
        total = stats["total"]
        passed = stats["passed"]
        failed = stats["failed"]
        pending = stats["pending"]
        acc = f"{100*passed/max(1,total-pending):.0f}%" if total > pending else "—"
        print(f"  {ds:<24} {total:>5} {passed:>5} {failed:>5} {pending:>5} {acc:>7}")
    print("=" * 68 + "\n")

    # Save results JSON
    out_path = DAB_RESULTS_DIR / "accuracy_report.json"
    DAB_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(accuracy, f, indent=2)
    print(f"  [Report] Saved to: {out_path}\n")


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run DataAgentBench queries through SpiderDIN.")
    parser.add_argument("--all", action="store_true", help="Run all 54 queries")
    parser.add_argument("--dataset", type=str, default=None, help="Run a specific dataset")
    parser.add_argument("--query_id", type=str, default=None, help="Run a specific query ID")
    parser.add_argument("--dab_repo", type=str, default=DAB_REPO_DEFAULT)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--skip_docker", action="store_true", help="Skip Docker-dependent datasets")
    parser.add_argument("--force", action="store_true", help="Re-run already evaluated queries")
    parser.add_argument("--report_only", action="store_true", help="Only print accuracy report")
    parser.add_argument(
        "--self_improve",
        action="store_true",
        help="Run the self-improving loop (extract rules from failures, activate, re-run, compare)",
    )
    args = parser.parse_args()

    # Load query index
    try:
        all_queries = load_all_queries(args.dab_repo)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print(f"\nPlease clone the DataAgentBench repo first:")
        print(f"  git lfs install")
        print(f"  git clone https://github.com/ucbepic/DataAgentBench.git {args.dab_repo}")
        sys.exit(1)

    summarize_queries(all_queries)

    if args.report_only:
        print_summary([], all_queries)
        return

    if args.self_improve:
        from backend.app.core.rules.self_improving_loop import SelfImprovingLoop
        loop = SelfImprovingLoop(dab_repo=args.dab_repo)
        result = loop.run_daily()
        print(f"\n[SelfImprove] status: {result['status']}")
        if result.get("run"):
            run = result["run"]
            print(f"  date        : {run['date']}")
            print(f"  rounds done : {len(run['rounds'])}")
            print(f"  final pass  : {run['final_passes']}/{run['total']} ({run['pass_rate']}%)")
            for r in run["rounds"]:
                delta_str = f"+{r['delta']}" if r['delta'] > 0 else str(r['delta'])
                print(
                    f"  round {r['round']}: {r['status']:16s}  "
                    f"delta={delta_str:>3}  rules={r.get('new_rules_added',0)}  "
                    f"elapsed={r.get('elapsed_s',0):.0f}s"
                )
        if result.get("rule_counts"):
            rc = result["rule_counts"]
            print(
                f"  rules → ACTIVE:{rc.get('ACTIVE',0)}  "
                f"REJECTED:{rc.get('REJECTED',0)}  "
                f"INACTIVE:{rc.get('INACTIVE',0)}"
            )
        if result.get("saturated"):
            print("  [SATURATED] Pipeline has converged — no further daily runs needed.")
        return

    if not (args.all or args.dataset or args.query_id):
        print("Please specify --all, --dataset <name>, or --dataset <name> --query_id <id>")
        parser.print_help()
        sys.exit(1)

    results = run_all(
        queries=all_queries,
        workers=args.workers,
        skip_docker=args.skip_docker,
        dataset_filter=args.dataset,
        query_id_filter=args.query_id,
        force_rerun=args.force,
    )

    print_summary(results, all_queries)


if __name__ == "__main__":
    main()
