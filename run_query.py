"""
Run a single DAB query from the terminal with live logs.

Examples:
  python run_query.py --dataset patents --id 1
  python run_query.py --dataset music_brainz_20k --id 3
  python run_query.py --list
"""

import sys, os, time, argparse, pathlib

# Force line-buffered stdout so log lines appear immediately in the terminal
os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, "backend/agent")

from agent.app.dab.benchmark_loader import load_all_queries

DAB_PATH = pathlib.Path("c:/Users/VikasVijigiri/Documents/DataAgentBench")

def main():
    parser = argparse.ArgumentParser(description="Run a single DAB query")
    parser.add_argument("--dataset", "-d", help="Dataset name (e.g. patents, music_brainz_20k)")
    parser.add_argument("--id", "-i", help="Query ID (e.g. 1, 3)")
    parser.add_argument("--list", "-l", action="store_true", help="List all available queries")
    parser.add_argument("--run", "-r", type=int, default=99, help="Run slot number (default: 99 = test run, not saved to DB)")
    args = parser.parse_args()

    queries = load_all_queries(DAB_PATH)

    if args.list:
        print(f"\n{'DATASET':<30} {'ID':<6} QUESTION")
        print("-" * 90)
        for q in queries:
            print(f"{q['dataset']:<30} {q['query_id']:<6} {q['question'][:60]}")
        return

    if not args.dataset or not args.id:
        parser.error("--dataset and --id are required (or use --list to see all queries)")

    matches = [q for q in queries if q["dataset"] == args.dataset and q["query_id"] == args.id]
    if not matches:
        print(f"No query found: dataset='{args.dataset}' id='{args.id}'")
        print("Run with --list to see all available queries.")
        sys.exit(1)

    q = matches[0]
    print(f"\nDataset : {q['dataset']}")
    print(f"Query ID: {q['query_id']}")
    print(f"Question: {q['question']}")
    print(f"GT      : {str(q.get('ground_truth', ''))[:200]}")
    print(f"Run slot: {args.run}  (slot 99 = test, not written to eval DB)")
    print("=" * 70)

    from agent.app.utils.llm import LLMClient
    from agent.app.dab.dab_orchestrator import run_dab_query

    llm = LLMClient(temperature=0.0)
    t0 = time.time()
    result = run_dab_query(q, llm_client=llm, run_number=args.run)
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
