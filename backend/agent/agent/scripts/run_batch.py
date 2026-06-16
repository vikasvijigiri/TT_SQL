import json
import os
import sys
import argparse
import traceback
import time
import warnings
from multiprocessing import Pool, cpu_count
from pathlib import Path

# Suppress Python 3.14 / Pydantic compatibility warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from agent.app.core.config import INPUT_DIR, RESULTS_DIR, get_db_path
import contextlib

# Defaults Ã¢â‚¬â€ overridden by --dialect / --input CLI args at runtime
_DEFAULT_DIALECT = "snowflake"
_DEFAULT_INPUT = str(INPUT_DIR / "spider2-lite-snowflake.jsonl")

# Module-level runtime config populated by main() before multiprocessing fan-out
_RUNTIME_DIALECT = _DEFAULT_DIALECT


def run_single_example(example: dict) -> dict:
    from agent.app.core.orchestrator import SemanticDINOrchestrator
    from agent.app.utils.logger import logger

    instance_id = example["instance_id"]
    db_name = example["db"]
    question = example["question"]
    external_knowledge = example.get("external_knowledge")
    dialect = example.get("_dialect", _RUNTIME_DIALECT)

    save_dir = os.path.join(str(RESULTS_DIR), db_name.upper())
    os.makedirs(save_dir, exist_ok=True)
    md_path = os.path.join(save_dir, f"{instance_id}.md")
    sql_path = os.path.join(save_dir, f"{instance_id}.sql")
    csv_path = os.path.join(save_dir, f"{instance_id}.csv")

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
            dialect=dialect,
            max_retries=3,
        )

        final_sql = orchestrator.execute_query(
            question, instance_id, external_knowledge=external_knowledge
        )

        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(final_sql)
        logger.success(f"Saved {instance_id}.sql")

        row_count = 0
        if os.path.exists(csv_path):
            with open(csv_path, encoding="utf-8", errors="replace") as cf:
                row_count = max(0, sum(1 for _ in cf) - 1)

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
        logger.error(f"Execution failed for {instance_id}: {e!s}")
        traceback.print_exc()
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
        if "orchestrator" in locals():
            with contextlib.suppress(Exception):
                orchestrator.executor.close()
        logger.stop_live_task_log()


def load_examples(
    input_file: str,
    instance_filter: list | None,
    db_filter: str | None,
    n: int,
    dialect: str,
) -> list[dict]:
    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found at {input_file}")
        sys.exit(1)

    all_examples = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                ex = json.loads(line)
                ex["_dialect"] = (
                    dialect  # stamp dialect so subprocess workers pick it up
                )
                all_examples.append(ex)

    if instance_filter:
        matched = [e for e in all_examples if e["instance_id"] in instance_filter]
        if not matched:
            print(f"ERROR: No matched instance_ids found in {input_file}")
            sys.exit(1)
        return matched

    if db_filter:
        matched = [e for e in all_examples if e["db"].upper() == db_filter.upper()]
        if not matched:
            print(f"ERROR: No examples found for db='{db_filter}' in {input_file}")
            sys.exit(1)
        return matched

    return all_examples[:n] if n > 0 else all_examples


def print_summary(results: list[dict]) -> None:
    ok = [r for r in results if r["status"] == "success"]
    empty = [r for r in results if r["status"] == "empty"]
    err = [r for r in results if r["status"] == "error"]

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
        icon = (
            "OK "
            if r["status"] == "success"
            else ("EMT" if r["status"] == "empty" else "ERR")
        )
        rows = r.get("row_count", 0)
        print(
            f"  [{icon}] {r['instance_id']:<20} {r['db']:<12} {rows:>6} rows  {r['elapsed_s']:>5}s"
        )
    print("=" * 68 + "\n")


def main() -> None:
    global _RUNTIME_DIALECT
    parser = argparse.ArgumentParser(
        description="Run Semantic DIN-SQL batch evaluation."
    )
    parser.add_argument(
        "--instance",
        type=str,
        action="append",
        default=None,
        help="Run specific instance_id(s)",
    )
    parser.add_argument("--db", type=str, default=None, help="Filter by database name")
    parser.add_argument(
        "--n", type=int, default=3, help="Max examples to run (0 = all)"
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Parallel workers (0 = cpu_count)"
    )
    parser.add_argument(
        "--dialect",
        type=str,
        default=_DEFAULT_DIALECT,
        help=f"Target SQL dialect (default: {_DEFAULT_DIALECT})",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=_DEFAULT_INPUT,
        help="Path to .jsonl benchmark input file",
    )
    args = parser.parse_args()

    _RUNTIME_DIALECT = args.dialect

    examples = load_examples(args.input, args.instance, args.db, args.n, args.dialect)
    num_workers = cpu_count() if args.workers == 0 else args.workers
    num_workers = min(num_workers, len(examples))

    print(f"\n{'=' * 68}")
    print("  Semantic DIN-SQL Batch Runner")
    print(f"  Dialect  : {args.dialect}")
    print(f"  Input    : {args.input}")
    print(f"  Examples : {len(examples)}")
    print(f"  Workers  : {num_workers}")
    print(f"{'=' * 68}\n")

    if num_workers == 1:
        results = [run_single_example(ex) for ex in examples]
    else:
        with Pool(processes=num_workers) as pool:
            results = pool.map(run_single_example, examples)

    print_summary(results)


if __name__ == "__main__":
    main()
