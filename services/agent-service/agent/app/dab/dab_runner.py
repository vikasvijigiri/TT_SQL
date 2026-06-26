"""

dab_runner.py

-------------

Batch runner for all 54 DataAgentBench queries.



Usage:

    python services/agent-service/agent/app/dab/dab_runner.py --all

    python services/agent-service/agent/app/dab/dab_runner.py --dataset bookreview

    python services/agent-service/agent/app/dab/dab_runner.py --dataset bookreview --query_id 1

    python services/agent-service/agent/app/dab/dab_runner.py --skip_docker   # Only SQLite + DuckDB datasets

"""



import sys

import json

import asyncio

import os
import argparse

from pathlib import Path

from typing import List, Dict, Any, Optional

from concurrent.futures import ThreadPoolExecutor, as_completed



# Add project root to path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

sys.path.insert(0, str(ROOT_DIR))



from agent.app.dab.benchmark_loader import load_all_queries, summarize_queries

from agent.app.dab.dab_orchestrator import run_dab_query

from agent.app.dab.dab_evaluator import compute_accuracy

from agent.services.llm import LLMClient

from agent.app.core.config import DAB_REPO, DAB_RESULTS_DIR

from agent.app.db.database import SessionLocal

from agent.app.db.models import TaskRun

import uuid

import contextlib



DAB_REPO_DEFAULT = str(DAB_REPO)





def print_progress_bar(

    current: int, total: int, prefix: str = "", width: int = 40

) -> None:

    filled = int(width * current / total) if total > 0 else 0

    bar = "#" * filled + "." * (width - filled)

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

    Files are always 1-indexed: query1_run1.md, query1_run2.md, ... query1_runN.md.

    """

    from agent.app.dab.dab_evaluator import load_eval_result as _load_eval



    # Reset cancellation flags to prevent stale states from stopping the run

    try:

        from agent.app.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG

        DAB_CANCEL_FLAG.set(False)

        SPIDER_CANCEL_FLAG.set(False)

    except Exception:

        pass



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

    # Run numbers are 1-indexed: _run1, _run2, ..., _runN (no bare query1.md)

    work: List[tuple] = []

    for q in filtered:

        for r in range(1, num_runs + 1):

            run_sfx = f"_run{r}"

            if not force_rerun:

                ev = _load_eval(q["dataset"], q["query_id"], run_suffix=run_sfx)

                if ev is not None:

                    tag = "PASS" if ev.get("passed") else "FAIL"

                    print(

                        f"  [SKIP] {q['instance_id']} run {r} (already evaluated: {tag})"

                    )

                    continue

            work.append((q, r))



    if not work:

        print("\n[OK] All query runs already evaluated. Use --force to re-run.")

        return []



    total_slots = len(work)

    print(f"\n[RUN] {total_slots} work items  (queries x runs, workers={workers})")

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

            print("[ENQUEUE] Finished enqueuing. Start workers via: python services/agent-service/workers/dab/dab_worker.py")

        finally:

            db.close()

        return []



    llm_client = LLMClient()



    if async_concurrent:

        # workers==1 is the default "unset" value - treat as uncapped (0) so all queries

        # truly run in parallel threads.  --workers N > 1 explicitly caps concurrency.

        _max_conc = workers if workers > 1 else 0

        results = asyncio.run(run_all_concurrent(work, llm_client, max_concurrent=_max_conc))

        for result in results:

            if isinstance(result, dict):

                reason_safe = (result.get('reason') or "")[:80].encode('ascii', 'replace').decode('ascii')

                error_safe = (result.get('error') or "")[:80].encode('ascii', 'replace').decode('ascii')

                if result["status"] == "passed":

                    print(f"\n  [PASS] {reason_safe}")

                elif result["status"] == "error":

                    print(f"\n  [ERROR] {error_safe}")

                else:

                    print(f"\n  [FAIL] {reason_safe}")

        print_summary(results, queries)

        return results



    if workers == 1:

        for i, (q, r) in enumerate(work, 1):

            label = f"run {r}" if num_runs > 1 else ""

            print(f"\n[{i}/{total_slots}] {q['instance_id']} {label}".rstrip())

            print_progress_bar(i - 1, total_slots, prefix="Progress")

            result = run_dab_query(q, llm_client=llm_client, run_number=r)

            results.append(result)

            reason_str = (result.get('reason') or "")[:80]

            error_str = (result.get('error') or "")[:80]

            if result["status"] == "passed":

                print(f"\n  [PASS] {reason_str}")

            elif result["status"] == "error":

                print(f"\n  [ERROR] {error_str}")

            else:

                print(f"\n  [FAIL] {reason_str}")

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

    print("  DAB BENCHMARK RESULTS - SpiderDIN / TT_SQL_V2")

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



    # Ensure evals_dir exists for this run

    import agent.app.dab.dab_evaluator as de

    from agent.app.core.config import get_user_dab_evals_dir, DEFAULT_USERNAME

    username = getattr(de, "DAB_RUN_USERNAME", None) or DEFAULT_USERNAME

    run_id = getattr(de, "DAB_RUN_ID", None) or "run_live"

    evals_dir = get_user_dab_evals_dir(username) / run_id

    evals_dir.mkdir(parents=True, exist_ok=True)



    # Save results JSON

    out_path = evals_dir / "accuracy_report.json"

    with open(out_path, "w", encoding="utf-8") as f:

        json.dump(accuracy, f, indent=2)

    print(f"  [Report] Saved to: {out_path}\n")



    # Regression gate - warn if pass@1 dropped vs previous run

    try:

        import glob as _glob

        _prev_reports = sorted(

            _glob.glob(str(get_user_dab_evals_dir(username) / "*" / "accuracy_report.json"))

        )

        # Remove current one if it was just picked up

        _prev_reports = [p for p in _prev_reports if str(out_path) != p]

        

        if _prev_reports:

            import json as _json2

            with open(_prev_reports[-1], "r", encoding="utf-8") as _f:

                _prev = _json2.load(_f)

            _cur_p1 = float(str(accuracy.get("pass_at_1_pct", "0")).replace("%", ""))

            _prev_p1 = float(str(_prev.get("pass_at_1_pct", "0")).replace("%", ""))

            if _cur_p1 < _prev_p1:

                print(

                    f"  [REGRESSION GATE] [!]  pass@1 dropped: {_prev_p1:.1f}% -> {_cur_p1:.1f}%  "

                    f"({_prev_p1 - _cur_p1:.1f} pp regression vs previous report)\n"

                )

            else:

                print(f"  [REGRESSION GATE] OK - pass@1 {_cur_p1:.1f}% (>= prev {_prev_p1:.1f}%)\n")

        # Archive this report with a timestamp for future comparisons

        import shutil as _shutil

        import time as _time

        _ts = _time.strftime("%Y%m%d_%H%M%S")

        _shutil.copy2(str(out_path), str(evals_dir / f"accuracy_report_{_ts}.json"))

    except Exception as _rge:

        print(f"  [REGRESSION GATE] Could not compare runs: {_rge}\n")



    # Generate Dynamic Analytics Dashboard

    try:

        from agent.app.core.meta.analytics_engine import generate_analytics_report

        generate_analytics_report(_results, evals_dir)

    except Exception as e:

        print(f"  [Analytics] Could not load Analytics Engine: {e}")





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

    parser.add_argument("--run_id", type=str, default=None, help="Run ID for tracking (default: auto-generated timestamp)")

    parser.add_argument("--username", type=str, default=os.environ.get("DEFAULT_USERNAME", "anonymous"), help="Username for result scoping")

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



    # Set run_id for tracking in the evaluations DB AND in the cache so

    # get_active_results_dir() uses the same ID (cache takes priority over module attr)

    import time as _time

    import agent.app.dab.dab_evaluator as _de

    _run_id = args.run_id or f"run_{_time.strftime('%Y%m%d_%H%M%S')}"

    _username = getattr(args, "username", "anonymous") or "anonymous"

    _de.DAB_RUN_ID = _run_id

    _de.DAB_RUN_USERNAME = _username

    try:

        from agent.app.utils.cache import cache_service

        cache_service.set("shared_DAB_RUN_ID", _run_id, ttl=86400)

        cache_service.set("shared_DAB_RUN_USERNAME", _username, ttl=86400)

        cache_service.set("shared_BENCHMARK", "dab", ttl=86400)

    except Exception:

        pass

    print(f"\n[RUN] Run ID: {_run_id}  |  Username: {_username}")



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

                f"  rules => ACTIVE:{rc.get('ACTIVE', 0)}  "

                f"REJECTED:{rc.get('REJECTED', 0)}  "

                f"INACTIVE:{rc.get('INACTIVE', 0)}"

            )

        if result.get("saturated"):

            print(

                "  [SATURATED] Pipeline has converged -- no further daily runs needed."

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



    # Trigger Post-Batch Meta-Learner

    try:

        from agent.app.core.meta.post_batch_meta_learner import PostBatchMetaLearner

        learner = PostBatchMetaLearner()

        learner.run_post_batch_analysis()

    except Exception as e:

        print(f"\n[Warning] Post-Batch Meta-Learner failed: {e}")





if __name__ == "__main__":

    main()

