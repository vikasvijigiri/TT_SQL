"""
CLI runner for a single DAB query.

Usage:
  python backend/agent/agent/dab_runner.py --dataset deps_dev_v1 --id 1
  python backend/agent/agent/dab_runner.py --dataset patents --id 1
  python backend/agent/agent/dab_runner.py --list
"""

import sys, os, time, argparse, pathlib

os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)

# Make the agent package importable when running this file directly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.app.dab.benchmark_loader import load_all_queries

DAB_PATH = pathlib.Path("c:/Users/VikasVijigiri/Documents/DataAgentBench")


def main():
    parser = argparse.ArgumentParser(description="Run a single DAB query with live logs")
    parser.add_argument("--dataset", "-d", help="Dataset name  e.g. deps_dev_v1, patents")
    parser.add_argument("--id",      "-i", help="Query ID  e.g. 1, 2")
    parser.add_argument("--list",    "-l", action="store_true", help="List all queries")
    parser.add_argument("--run",     "-r", type=int, default=99,
                        help="Run slot (default 99 = test, not saved to eval DB)")
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

    q = matches[0]
    print(f"\nDataset : {q['dataset']}")
    print(f"Query ID: {q['query_id']}")
    print(f"Question: {q['question']}")
    print(f"GT      : {str(q.get('ground_truth', ''))[:200]}")
    print("=" * 70)

    # Reset cancellation flags to prevent stale states from stopping the run
    try:
        from agent.app.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG
        DAB_CANCEL_FLAG.set(False)
        SPIDER_CANCEL_FLAG.set(False)
    except Exception:
        pass

    from agent.app.utils.llm import LLMClient
    from agent.app.dab.dab_orchestrator import run_dab_query

    t0 = time.time()
    result = run_dab_query(q, llm_client=LLMClient(temperature=0.0), run_number=args.run)
    elapsed = time.time() - t0

    print("=" * 70)
    print(f"ELAPSED : {elapsed:.1f}s")
    print(f"PASSED  : {result['passed']}")
    print(f"ANSWER  : {str(result.get('agent_answer', ''))[:300]}")
    print(f"STATUS  : {result.get('status')}")
    if result.get("error"):
        print(f"ERROR   : {result['error']}")


if __name__ == "__main__":
    main()
