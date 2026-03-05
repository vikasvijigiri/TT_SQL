"""
csv_to_spider2_jsonl.py
-----------------------
Converts a CSV file into the spider2-lite JSONL format.

Expected CSV columns:
  - 'questions' : The natural-language question
  - 'db'        : The database identifier

Output JSONL fields per record:
  {
    "instance_id": "q001",          # zero-padded auto-incremented ID
    "db":          "<db value>",
    "question":    "<question text>",
    "external_knowledge": null
  }

Usage:
  python csv_to_spider2_jsonl.py                        # uses default paths
  python csv_to_spider2_jsonl.py input.csv output.jsonl # custom paths
"""

import csv
import json
import sys
from pathlib import Path


def csv_to_spider2_jsonl(
    input_csv: str = "data/name.csv",
    output_jsonl: str = "data/output.jsonl",
    questions_col: str = "questions",
    db_col: str = "db",
) -> None:
    input_path = Path(input_csv)
    output_path = Path(output_jsonl)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path.resolve()}")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    records_written = 0

    with input_path.open(newline="", encoding="utf-8") as csv_file, \
         output_path.open("w", encoding="utf-8") as jsonl_file:

        reader = csv.DictReader(csv_file)

        # Validate required columns
        if reader.fieldnames is None:
            print("[ERROR] CSV file appears to be empty.")
            sys.exit(1)

        missing = [c for c in (questions_col, db_col) if c not in reader.fieldnames]
        if missing:
            print(f"[ERROR] Missing expected column(s): {missing}")
            print(f"        Found columns: {list(reader.fieldnames)}")
            sys.exit(1)

        for idx, row in enumerate(reader, start=1):
            question = row[questions_col].strip()
            db = row[db_col].strip()

            if not question or not db:
                print(f"[WARN]  Row {idx} skipped — empty 'questions' or 'db' field.")
                continue

            record = {
                "instance_id": f"q{idx:03d}",
                "db": db,
                "question": question,
                "external_knowledge": None,
            }

            jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            records_written += 1

    print(f"[OK] {records_written} record(s) written to: {output_path.resolve()}")


if __name__ == "__main__":
    args = sys.argv[1:]
    input_csv  = args[0] if len(args) > 0 else "data/name.csv"
    output_jsonl = args[1] if len(args) > 1 else "data/output.jsonl"

    csv_to_spider2_jsonl(input_csv=input_csv, output_jsonl=output_jsonl)
