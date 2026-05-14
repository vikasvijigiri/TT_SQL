"""
run_batch.py — Semantic DIN-SQL Batch Runner
============================================
Usage:
  # Run a specific example by ID
  python run_batch.py --instance sf_bq070

  # Run all examples for a specific DB
  python run_batch.py --db IDC

  # Run first 5 examples sequentially
  python run_batch.py --n 5

  # Run first 10 examples with 4 parallel workers
  python run_batch.py --n 10 --workers 4

  # Run all examples for a DB using all CPU cores
  python run_batch.py --db PATENTS --workers 0
"""
import json
import os
import sys
import argparse
import traceback
import time
from multiprocessing import Pool, cpu_count
from src.agents.prompt_evolver import PromptEvolver
from src.utils.llm import LLMClient

BASE_DB_DIR = "resources/databases/snowflake"
INPUT_FILE  = "input_data/spider2-lite-snowflake.jsonl"


def get_db_path(db_name: str) -> str:
    """Finds the deepest directory containing JSON metadata files for a given DB."""
    db_root = os.path.join(BASE_DB_DIR, db_name)
    if not os.path.exists(db_root):
        raise ValueError(f"Database directory not found: {db_root}")
    for root, dirs, files in os.walk(db_root):
        if any(f.endswith('.json') for f in files):
            return root
    raise ValueError(f"No JSON metadata files found in {db_root}")


def run_single_example(example: dict) -> dict:
    """
    Fully self-contained worker — safe to run in a subprocess.
    Each call creates its own orchestrator, logger, and DB connection.
    """
    from src.core.orchestrator import SemanticDINOrchestrator
    from src.utils.logger import logger

    instance_id = example['instance_id']
    db_name     = example['db']
    question    = example['question']

    save_dir = os.path.join("results", db_name.upper())
    os.makedirs(save_dir, exist_ok=True)
    md_path  = os.path.join(save_dir, f"{instance_id}.md")
    sql_path = os.path.join(save_dir, f"{instance_id}.sql")
    csv_path = os.path.join(save_dir, f"{instance_id}.csv")

    # Clear stale results
    if os.path.exists(csv_path):
        os.remove(csv_path)

    logger.start_live_task_log(md_path)
    start = time.time()

    try:
        logger.log_section(f"{instance_id} (DB: {db_name})", color=logger.YELLOW)
        logger.info(f"Question: {question}")

        db_path = get_db_path(db_name)

        orchestrator = SemanticDINOrchestrator(
            db_directory=db_path,
            db_name=db_name,
            dialect="snowflake",
            max_retries=3,
        )

        final_sql = orchestrator.execute_query(question, instance_id)

        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(final_sql)
        logger.success(f"Saved {instance_id}.sql")

        # Check if CSV was produced and is non-empty
        csv_path = os.path.join(save_dir, f"{instance_id}.csv")
        row_count = 0
        if os.path.exists(csv_path):
            with open(csv_path, encoding="utf-8", errors="replace") as cf:
                row_count = max(0, sum(1 for _ in cf) - 1)  # subtract header

        elapsed = round(time.time() - start, 1)
        status = "success" if row_count > 0 else "empty"
        return {
            "instance_id": instance_id,
            "db": db_name,
            "status": status,
            "row_count": row_count,
            "elapsed_s": elapsed,
        }

    except Exception as e:
        logger.error(f"Execution failed for {instance_id}: {str(e)}")
        logger.debug(traceback.format_exc())
        elapsed = round(time.time() - start, 1)
        return {
            "instance_id": instance_id,
            "db": db_name,
            "status": "error",
            "row_count": 0,
            "error": str(e),
            "elapsed_s": elapsed,
        }
    finally:
        logger.stop_live_task_log()


def load_examples(instance_filter: str | None, db_filter: str | None, n: int) -> list[dict]:
    all_examples = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                all_examples.append(json.loads(line))

    if instance_filter:
        matched = [e for e in all_examples if e['instance_id'] in instance_filter]
        if not matched:
            print(f"ERROR: No matched instance_ids found in {INPUT_FILE}")
            sys.exit(1)
        return matched

    if db_filter:
        matched = [e for e in all_examples if e['db'].upper() == db_filter.upper()]
        if not matched:
            print(f"ERROR: No examples found for db='{db_filter}' in {INPUT_FILE}")
            sys.exit(1)
        print(f"Found {len(matched)} examples for db='{db_filter}'")
        return matched

    return all_examples[:n] if n > 0 else all_examples


def print_summary(results: list[dict]):
    ok    = [r for r in results if r['status'] == 'success']
    empty = [r for r in results if r['status'] == 'empty']
    err   = [r for r in results if r['status'] == 'error']

    print("\n" + "=" * 68)
    print("  BATCH SUMMARY")
    print("=" * 68)
    print(f"  Total   : {len(results)}")
    print(f"  Success : {len(ok)}  (non-empty CSV)")
    print(f"  Empty   : {len(empty)}  (0 rows)")
    print(f"  Errors  : {len(err)}  (execution error)")
    print("-" * 68)
    print(f"  {'ID':<22} {'DB':<12} {'Status':<8} {'Rows':>6} {'Time':>7}")
    print("-" * 68)
    for r in results:
        icon = "OK " if r['status'] == 'success' else ("EMT" if r['status'] == 'empty' else "ERR")
        rows = r.get('row_count', 0)
        print(f"  [{icon}] {r['instance_id']:<20} {r['db']:<12} {rows:>6} rows  {r['elapsed_s']:>5}s")
    print("=" * 68 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run Semantic DIN-SQL on Spider2-Lite Snowflake benchmark.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--instance", type=str, action='append', default=None,
                        help="Run specific instance_id(s) (can be used multiple times)")
    parser.add_argument("--db", type=str, default=None,
                        help="Run ALL instances for a specific database name (e.g., IDC, PATENTS)")
    parser.add_argument("--n", type=int, default=3,
                        help="Number of examples to run (default: 3; use 0 for ALL; ignored if --instance or --db is set)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel worker processes (default: 1=sequential; 0=all CPU cores)")
    args = parser.parse_args()

    examples = load_examples(args.instance, args.db, args.n)
    num_workers = cpu_count() if args.workers == 0 else args.workers
    num_workers = min(num_workers, len(examples))

    print(f"\n{'='*68}")
    print(f"  Semantic DIN-SQL Batch Runner")
    print(f"  Examples : {len(examples)}")
    if args.db:
        print(f"  Database : {args.db.upper()}")
    print(f"  Workers  : {num_workers} ({'sequential' if num_workers == 1 else 'parallel'})")
    print(f"{'='*68}\n")

    if num_workers == 1:
        results = [run_single_example(ex) for ex in examples]
    else:
        with Pool(processes=num_workers) as pool:
            results = pool.map(run_single_example, examples)

    print_summary(results)
    
    # Autonomous Evolution Step
    try:
        print("Starting Autonomous Prompt Evolution...")
        llm = LLMClient()
        evolver = PromptEvolver(llm)
        evolver.evolve_prompts(log_file="resources/logs/major_failures.log") # Learn from major failures
        print("✅ Evolution complete.")
    except Exception as e:
        print(f"⚠️ Evolution skipped: {e}")


if __name__ == "__main__":
    main()
