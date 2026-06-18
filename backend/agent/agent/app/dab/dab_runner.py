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
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.app.dab.benchmark_loader import load_all_queries, summarize_queries
from agent.app.dab.dab_orchestrator import run_dab_query, DAB_RESULTS_DIR
from agent.app.dab.dab_evaluator import compute_accuracy
from agent.app.utils.llm import LLMClient
from agent.app.core.config import DAB_REPO
from agent.app.db.database import SessionLocal
from agent.app.db.models import TaskRun
import uuid
import contextlib

DAB_REPO_DEFAULT = str(DAB_REPO)


def print_progress_bar(
    current: int, total: int, prefix: str = "", width: int = 40
) -> None:
    filled = int(width * current / total) if total > 0 else 0
    bar = "Ã¢â€“Ë†" * filled + "Ã¢â€“â€˜" * (width - filled)
    pct = 100 * current / total if total > 0 else 0
    print(f"\r{prefix} [{bar}] {current}/{total} ({pct:.0f}%)", end="", flush=True)


async def _run_query_async(
    loop: asyncio.AbstractEventLoop,
    thread_pool: ThreadPoolExecutor,
    q: Dict[str, Any],
    llm_client: Any,
    r: int,
) -> Dict[str, Any]:
    """Wrap the sync run_dab_query so it's awaitable without blocking the event loop.

    The LLM calls inside are I/O-bound network requests; Python's GIL is released
    during socket waits, so multiple threads make real parallel progress.
    """
    try:
        return await loop.run_in_executor(thread_pool, run_dab_query, q, llm_client, r)
    except Exception as exc:
        return {
            "dataset": q["dataset"],
            "query_id": q["query_id"],
            "run_number": r,
            "status": "error",
            "passed": False,
            "error": str(exc),
        }


async def run_all_concurrent(
    work: List[tuple],
    llm_client: Any,
    max_concurrent: int = 0,
) -> List[Dict[str, Any]]:
    """Run all work items concurrently using asyncio + thread pool.

    max_concurrent=0 means one thread per work item (fully parallel).
    Uses asyncio.gather so the event loop interleaves I/O waits efficiently.
    """
    n = max_concurrent if max_concurrent > 0 else len(work)
    loop = asyncio.get_event_loop()
    thread_pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix="dab_async")
    print(f"\n[ASYNC] Running {len(work)} queries concurrently (max_workers={n})")
    print("-" * 60)
    try:
        tasks = [_run_query_async(loop, thread_pool, q, llm_client, r) for q, r in work]
        results = await asyncio.gather(*tasks)
    finally:
        thread_pool.shutdown(wait=True)
    return list(results)


def run_all(
    queries: List[Dict[str, Any]],
    workers: int = 1,
    skip_docker: bool = False,
    dataset_filter: Optional[str] = None,
    query_id_filter: Optional[str] = None,
    force_rerun: bool = False,
    num_runs: int = 1,
    enqueue_only: bool = False,
    async_concurrent: bool = False,
) -> List[Dict[str, Any]]:
    """Run all (or filtered) queries and return results.

    num_runs: how many independent runs per query (default 1).
    Run 0 saves to canonical files; runs 1..N-1 save with _run{N} suffix.
    """
    from agent.app.dab.dab_evaluator import load_eval_result as _load_eval

    # Apply filters
    filtered = queries
    if skip_docker:
        filtered = [q for q in filtered if not q["needs_docker"]]
        print(
            f"[skip_docker] Filtered to {len(filtered)} queries (SQLite + DuckDB only)"
        )
    if dataset_filter:
        filtered = [
            q for q in filtered if q["dataset"].lower() == dataset_filter.lower()
        ]
    if query_id_filter:
        filtered = [q for q in filtered if q["query_id"] == str(query_id_filter)]

    # Build (query, run_number) work items; skip already-completed slots
    work: List[tuple] = []
    for q in filtered:
        for r in range(num_runs):
            run_sfx = f"_run{r}" if r > 0 else ""
            if not force_rerun:
                ev = _load_eval(q["dataset"], q["query_id"], run_suffix=run_sfx)
                if ev is not None:
                    tag = "PASS" if ev.get("passed") else "FAIL"
                    label = f"run {r}" if r > 0 else "run 0"
                    print(
                        f"  [SKIP] {q['instance_id']} {label} (already evaluated: {tag})"
                    )
                    continue
            work.append((q, r))

    if not work:
        print("\n[OK] All query runs already evaluated. Use --force to re-run.")
        return []

    total_slots = len(work)
    print(f"\n[RUN] {total_slots} work items  (queries Ãƒâ€” runs, workers={workers})")
    print("-" * 60)

    results = []
    
    if enqueue_only:
        db = SessionLocal()
        try:
            print(f"\\n[ENQUEUE] Pushing {total_slots} items to TaskManager Queue...")
            for q, r in work:
                task_id = f"dab_{uuid.uuid4().hex[:8]}"
                target_id = f"{q['dataset']}_{q['query_id']}_run{r}"
                
                # Upsert to prevent duplicates if someone runs enqueue twice
                existing = db.query(TaskRun).filter(TaskRun.target_id == target_id, TaskRun.status == "PENDING").first()
                if not existing:
                    tr = TaskRun(
                        id=task_id,
                        task_type="dab_query",
                        status="PENDING",
                        target_id=target_id
                    )
                    db.add(tr)
            db.commit()
            print("[ENQUEUE] Finished enqueuing. Start workers via: python backend/app/workers/dab_worker.py")
        finally:
            db.close()
        return []

    llm_client = LLMClient()

    if async_concurrent:
        # workers==1 is the default "unset" value — treat as uncapped (0) so all queries
        # truly run in parallel threads.  --workers N > 1 explicitly caps concurrency.
        _max_conc = workers if workers > 1 else 0
        results = asyncio.run(run_all_concurrent(work, llm_client, max_concurrent=_max_conc))
        for result in results:
            if isinstance(result, dict):
                if result["status"] == "passed":
                    print(f"\n  [PASS] {result.get('reason', '')[:80]}")
                elif result["status"] == "error":
                    print(f"\n  [ERROR] {result.get('error', '')[:80]}")
                else:
                    print(f"\n  [FAIL] {result.get('reason', '')[:80]}")
        print_summary(results, queries)
        return results

    if workers == 1:
        for i, (q, r) in enumerate(work, 1):
            label = f"run {r}" if num_runs > 1 else ""
            print(f"\n[{i}/{total_slots}] {q['instance_id']} {label}".rstrip())
            print_progress_bar(i - 1, total_slots, prefix="Progress")
            result = run_dab_query(q, llm_client=llm_client, run_number=r)
            results.append(result)
            if result["status"] == "passed":
                print(f"\n  [PASS] {result['reason'][:80]}")
            elif result["status"] == "error":
                print(f"\n  [ERROR] {result.get('error', '')[:80]}")
            else:
                print(f"\n  [FAIL] {result['reason'][:80]}")
            print_summary(results, queries)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_dab_query, q, llm_client, r): (q, r)
                for q, r in work
            }
            completed = 0
            for future in as_completed(futures):
                completed += 1
                print_progress_bar(completed, total_slots, prefix="Progress")
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    q, r = futures[future]
                    results.append(
                        {
                            "dataset": q["dataset"],
                            "query_id": q["query_id"],
                            "run_number": r,
                            "status": "error",
                            "passed": False,
                            "error": str(e),
                        }
                    )
                print_summary(results, queries)

    print("\n")
    return results


def print_summary(
    _results: List[Dict[str, Any]], all_queries: List[Dict[str, Any]]
) -> None:
    """Print benchmark summary matching Claude's pass@1 / pass@K format."""
    accuracy = compute_accuracy(all_queries)
    k = accuracy.get("num_runs", 1)
    slots = accuracy.get("total_run_slots", accuracy["evaluated"])
    passing = accuracy.get("passing_run_slots", 0)
    accuracy.get("queries_passed_atk", 0)

    print("\n" + "=" * 72)
    print("  DAB BENCHMARK RESULTS Ã¢â‚¬â€ SpiderDIN / TT_SQL_V2")
    print("=" * 72)
    print(f"  Total Queries  : {accuracy['total_queries']}")
    print(
        f"  Evaluated      : {accuracy['evaluated']}  (pending: {accuracy['pending']})"
    )
    print(f"  Run slots      : {passing}/{slots} passed  (K={k} runs per query)")
    print(f"  pass@1         : {accuracy['pass_at_1_pct']}  (run-slot success rate)")
    print(
        f"  pass@{k}         : {accuracy['pass_at_k_pct']}  (query-level: any run passes)"
    )
    print("-" * 72)
    print(f"  {'Dataset':<25} {'Queries':>7} {'pass@1':>8} {'pass@' + str(k):>8}")
    print("-" * 72)
    for ds, stats in sorted(accuracy["per_dataset"].items()):
        n = stats["total"]
        p1 = stats.get("pass_at_1_pct", "N/A")
        pk = stats.get("pass_at_k_pct", "N/A")
        pend = stats.get("pending", 0)
        pend_str = f"  ({pend} pending)" if pend else ""
        print(f"  {ds:<25} {n:>7} {p1:>8} {pk:>8}{pend_str}")
    print("=" * 72 + "\n")

    # Save results JSON
    out_path = DAB_RESULTS_DIR / "accuracy_report.json"
    DAB_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(accuracy, f, indent=2)
    print(f"  [Report] Saved to: {out_path}\n")


def main():
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
    with contextlib.suppress(Exception):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run DataAgentBench queries through SpiderDIN."
    )
    parser.add_argument("--all", action="store_true", help="Run all 54 queries")
    parser.add_argument(
        "--dataset", type=str, default=None, help="Run a specific dataset"
    )
    parser.add_argument(
        "--query_id", type=str, default=None, help="Run a specific query ID"
    )
    parser.add_argument("--dab_repo", type=str, default=DAB_REPO_DEFAULT)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--skip_docker", action="store_true", help="Skip Docker-dependent datasets"
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-run already evaluated queries"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of independent runs per query (default 1)",
    )
    parser.add_argument(
        "--report_only", action="store_true", help="Only print accuracy report"
    )
    parser.add_argument(
        "--enqueue", action="store_true", help="Enqueue queries to the SQLite Task Queue instead of running them"
    )
    parser.add_argument(
        "--self_improve",
        action="store_true",
        help="Run the self-improving loop (extract rules from failures, activate, re-run, compare)",
    )
    parser.add_argument(
        "--async",
        dest="async_concurrent",
        action="store_true",
        help="Run all queries concurrently using asyncio + thread pool (non-blocking I/O). "
             "Faster than --workers N for I/O-bound LLM calls. Use --workers to cap parallelism.",
    )
    args = parser.parse_args()

    # Load query index
    try:
        all_queries = load_all_queries(args.dab_repo)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("\nPlease clone the DataAgentBench repo first:")
        print("  git lfs install")
        print(
            f"  git clone https://github.com/ucbepic/DataAgentBench.git {args.dab_repo}"
        )
        sys.exit(1)

    summarize_queries(all_queries)

    if args.report_only:
        print_summary([], all_queries)
        return

    if args.self_improve:
        from agent.app.core.rules.self_improving_loop import SelfImprovingLoop

        loop = SelfImprovingLoop(dab_repo=args.dab_repo)
        result = loop.run_daily()
        print(f"\n[SelfImprove] status: {result['status']}")
        if result.get("run"):
            run = result["run"]
            print(f"  date        : {run['date']}")
            print(f"  rounds done : {len(run['rounds'])}")
            print(
                f"  final pass  : {run['final_passes']}/{run['total']} ({run['pass_rate']}%)"
            )
            for r in run["rounds"]:
                delta_str = f"+{r['delta']}" if r["delta"] > 0 else str(r["delta"])
                print(
                    f"  round {r['round']}: {r['status']:16s}  "
                    f"delta={delta_str:>3}  rules={r.get('new_rules_added', 0)}  "
                    f"elapsed={r.get('elapsed_s', 0):.0f}s"
                )
        if result.get("rule_counts"):
            rc = result["rule_counts"]
            print(
                f"  rules Ã¢â€ â€™ ACTIVE:{rc.get('ACTIVE', 0)}  "
                f"REJECTED:{rc.get('REJECTED', 0)}  "
                f"INACTIVE:{rc.get('INACTIVE', 0)}"
            )
        if result.get("saturated"):
            print(
                "  [SATURATED] Pipeline has converged Ã¢â‚¬â€ no further daily runs needed."
            )
        return

    if not (args.all or args.dataset or args.query_id):
        print(
            "Please specify --all, --dataset <name>, or --dataset <name> --query_id <id>"
        )
        parser.print_help()
        sys.exit(1)

    results = run_all(
        queries=all_queries,
        workers=args.workers,
        skip_docker=args.skip_docker,
        dataset_filter=args.dataset,
        query_id_filter=args.query_id,
        force_rerun=args.force,
        num_runs=args.runs,
        enqueue_only=args.enqueue,
        async_concurrent=args.async_concurrent,
    )

    if args.enqueue:
        return

    print_summary(results, all_queries)


if __name__ == "__main__":
    main()
