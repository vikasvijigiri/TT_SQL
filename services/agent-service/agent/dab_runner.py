"""
CLI runner for a single DAB query.

Usage:
  python dab_runner.py --dataset crmarenapro --id 2
  python dab_runner.py --dataset deps_dev_v1 --id 1 --run-id run_20260624_1130
  python dab_runner.py --list
"""

import sys, os, time, argparse, pathlib
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["PYTHONUTF8"] = "1"
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Make the agent package importable when running this file directly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.app.dab.benchmark_loader import load_all_queries

from config.config import DAB_REPO
DAB_PATH = pathlib.Path(DAB_REPO)


def main():
    parser = argparse.ArgumentParser(description="Run a single DAB query with live logs")
    parser.add_argument("--dataset", "-d", help="Dataset name  e.g. deps_dev_v1, patents")
    parser.add_argument("--id",      "-i", help="Query ID  e.g. 1, 2")
    parser.add_argument("--list",    "-l", action="store_true", help="List all queries")
    parser.add_argument("--run",     "-r", type=int, default=0,
                        help="Legacy integer run slot (0 = no suffix). Prefer --run-id.")
    parser.add_argument("--run-id",  help=(
        "String run identifier stored under database/results/dab/vikas/<run-id>/. "
        "Auto-generated as run_YYYYMMDD_HHMM if omitted."
    ))
    parser.add_argument("--username", "-u", default=os.environ.get("DEFAULT_USERNAME", "anonymous"),
                        help="Username subfolder")
    args = parser.parse_args()

    queries = load_all_queries(DAB_PATH)

    if args.list:
        print(f"\n{'DATASET':<30} {'ID':<6} QUESTION")
        print("-" * 90)
        for q in queries:
            print(f"{q['dataset']:<30} {q['query_id']:<6} {q['question'][:60]}")
        return

    if not args.dataset or not args.id:
        parser.error("--dataset and --id are required  (or --list to see all queries)")

    matches = [q for q in queries if q["dataset"] == args.dataset and q["query_id"] == args.id]
    if not matches:
        print(f"No query found: dataset='{args.dataset}' id='{args.id}'")
        print("Use --list to see all available queries.")
        sys.exit(1)

    # Determine the run identifier: use --run-id if given, else auto-timestamp
    run_id = args.run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Inject into shared cache so get_active_results_dir() picks it up
    try:
        from agent.app.utils.cache import cache_service
        cache_service.set("shared_DAB_RUN_ID", run_id, ttl=86400)
        cache_service.set("shared_DAB_RUN_USERNAME", args.username, ttl=86400)
        cache_service.set("shared_BENCHMARK", "dab", ttl=86400)
    except Exception:
        pass

    q = matches[0]
    print(f"\nDataset : {q['dataset']}")
    print(f"Query ID: {q['query_id']}")
    print(f"Question: {q['question']}")
    print(f"GT      : {str(q.get('ground_truth', ""))[:200]}")
    print(f"Run ID  : {run_id}")
    print(f"Username: {args.username}")
    print("=" * 70)

    # Reset cancellation flags to prevent stale states from stopping the run
    try:
        from agent.app.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG
        DAB_CANCEL_FLAG.set(False)
        SPIDER_CANCEL_FLAG.set(False)
    except Exception:
        pass

    from agent.services.llm import LLMClient
    from agent.app.dab.dab_orchestrator import run_dab_query

    t0 = time.time()
    result = run_dab_query(q, llm_client=LLMClient(temperature=0.0), run_number=args.run)
    elapsed = time.time() - t0

    # Find and report the .md output path
    from agent.app.core.config import get_active_results_dir
    res_dir = get_active_results_dir() / q['dataset']
    _sfx = f"_run{args.run}" if args.run > 0 else ""
    md_file = res_dir / f"query{q['query_id']}{_sfx}.md"

    print("\n" + "=" * 70)
    print(f"ELAPSED : {elapsed:.1f}s")
    print(f"PASSED  : {result['passed']}")
    print(f"ANSWER  : {str(result.get('agent_answer', ""))[:300]}")
    print(f"STATUS  : {result.get('status')}")
    print(f"LOG     : {md_file}")
    if result.get("error"):
        print(f"ERROR   : {result['error']}")


if __name__ == "__main__":
    main()
