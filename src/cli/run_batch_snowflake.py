import argparse
import os

from dotenv import load_dotenv

from core.batch_runner import BatchRunner
from core.config import get_settings
from core.data_loader import DataLoader
from core.paths import DATA_DIR


def main():
    load_dotenv()
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Snowflake Batch Runner")
    parser.add_argument(
        "--dataset", type=str, default=str(DATA_DIR / "spider2-lite-snowflake.jsonl")
    )
    parser.add_argument("--model", type=str, default=settings.LLM_MODEL)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    os.environ["DB_TYPE"] = "snowflake"  # Explicit session setting

    tasks = DataLoader.load_jsonl(args.dataset)
    if args.limit > 0:
        tasks = tasks[: args.limit]

    runner = BatchRunner(
        model_name=args.model,
        workers=args.workers,
        overwrite=args.overwrite,
        use_rag=False,  # Use TableSelector by default
    )
    runner.run(tasks)


if __name__ == "__main__":
    main()
