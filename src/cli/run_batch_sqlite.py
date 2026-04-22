import argparse
import os

from dotenv import load_dotenv

from core.batch_runner import BatchRunner
from core.data_loader import DataLoader
from core.paths import DATA_DIR


def main():
    parser = argparse.ArgumentParser(description="SQLite Batch Runner")
    parser.add_argument(
        "--dataset", type=str, default=str(DATA_DIR / "spider2-lite-sqlite.jsonl")
    )
    parser.add_argument("--model", type=str, default=os.getenv("LLM_MODEL", "gpt-4o"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    os.environ["DB_TYPE"] = "sqlite"  # Explicit session setting

    tasks = DataLoader.load_jsonl(args.dataset)
    if args.limit > 0:
        tasks = tasks[: args.limit]

    runner = BatchRunner(
        model_name=args.model,
        workers=args.workers,
        overwrite=args.overwrite,
        use_rag=False,  # Default to semantic TableSelector
    )
    runner.run(tasks)


if __name__ == "__main__":
    main()
