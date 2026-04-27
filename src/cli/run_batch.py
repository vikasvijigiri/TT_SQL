import argparse
import os
import json
from pathlib import Path
from dotenv import load_dotenv

from core.batch_runner import BatchRunner
from core.config import get_settings
from core.paths import DATA_DIR

def load_jsonl(file_path):
    tasks = []
    if not os.path.exists(file_path):
        return tasks
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
    return tasks

def main():
    load_dotenv()
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Unified Batch Runner with DB filtering")
    parser.add_argument("--type", type=str, default="sqlite", choices=["sqlite", "snowflake", "bigquery"], help="Database type/dialect")
    parser.add_argument("--db", type=str, help="Specific database name to filter tasks by (e.g., 'IPL')")
    parser.add_argument("--ids", nargs="+", help="Specific instance IDs to run (space separated)")
    parser.add_argument("--dataset", type=str, help="Specific dataset file path (optional)")
    parser.add_argument("--model", type=str, default=settings.LLM_MODEL, help="Model name")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing results")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Set DB_TYPE for the session if not already in env
    os.environ["DB_TYPE"] = args.type

    # Determine default dataset if not provided
    if not args.dataset:
        if args.type == "sqlite":
            args.dataset = str(DATA_DIR / "spider2-lite-sqlite.jsonl")
        elif args.type == "snowflake":
            args.dataset = str(DATA_DIR / "spider2-lite-snowflake.jsonl")
        elif args.type == "bigquery":
            # Search both bigquery and general jsonl
            potential_file = DATA_DIR / "spider2-lite-bigquery.jsonl"
            if not potential_file.exists():
                potential_file = DATA_DIR / "spider2-lite.jsonl"
            args.dataset = str(potential_file)

    if not args.dataset or not os.path.exists(args.dataset):
        print(f"Error: Dataset file not found at {args.dataset}")
        return

    # Load and filter tasks
    tasks = load_jsonl(args.dataset)
    initial_count = len(tasks)
    
    if args.db:
        tasks = [t for t in tasks if str(t.get("db", "")).upper() == str(args.db).upper()]
        print(f"Filtered by DB ({args.db}): {len(tasks)} tasks.")
        
    if args.ids:
        tasks = [t for t in tasks if t.get("instance_id") in args.ids]
        print(f"Filtered by IDs: {len(tasks)} tasks.")
        
    if not args.db and not args.ids:
        print(f"Running all tasks in {args.dataset}. Total: {len(tasks)}")

    if args.limit > 0:
        tasks = tasks[:args.limit]

    if not tasks:
        print("No tasks found matching criteria.")
        return

    runner = BatchRunner(
        model_name=args.model,
        workers=args.workers,
        overwrite=args.overwrite,
        verbose=args.verbose
    )
    runner.run(tasks)

if __name__ == "__main__":
    main()
