
import os
import json
import glob
import time
from pathlib import Path

# Define root paths
BASE_DIR = Path(__file__).parent.parent.parent.parent # src/tt_sql/utils -> .../TT_SQL
OLD_RESULTS_DIR = BASE_DIR / "old_results"
GOLD_SQL_DIR = BASE_DIR / "gold" / "sql"
GOLD_CSV_DIR = BASE_DIR / "gold" / "exec_result"
JSON_LOGS_DIR = BASE_DIR / "JSON_logs"
SPIDER_DATA = BASE_DIR / "spider2-lite.jsonl"

def load_spider_questions():
    """Load questions from spider2-lite.jsonl into a dict {instance_id: question}"""
    questions = {}
    if not SPIDER_DATA.exists():
        print(f"Warning: {SPIDER_DATA} not found.")
        return questions
        
    with open(SPIDER_DATA, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    item = json.loads(line)
                    if "instance_id" in item and "question" in item:
                        questions[item["instance_id"]] = item["question"]
                except:
                    pass
    print(f"Loaded {len(questions)} questions from spider2-lite.jsonl")
    return questions

def collect_failures():
    """
    Collects failures based on files present in old_results/failed_examples.
    Algorithm:
    1. List IDs from old_results/failed_examples
    2. Get Question from spider2-lite.jsonl
    3. Get Generated SQL from old_results/sql/<id>.sql
    4. Get Execution Result from old_results/csv/<id>.csv
    5. Get Gold SQL from gold/sql/<id>.sql
    6. Get Gold CSV Result from gold/exec_result/<id>.csv
    """
    
    failures = []
    
    # Ensure output dir exists
    os.makedirs(JSON_LOGS_DIR, exist_ok=True)
    
    failed_dir = OLD_RESULTS_DIR / "failed_examples"
    if not failed_dir.exists():
        print(f"Error: {failed_dir} does not exist.")
        return

    print(f"Scanning {failed_dir} for failures...")
    
    # Get all files in failed_examples to extract IDs
    failed_files = list(failed_dir.glob("*"))
    failed_ids = set(f.stem for f in failed_files)
    
    print(f"Found {len(failed_ids)} unique failed IDs.")
    
    # Load Questions
    questions_map = load_spider_questions()
    
    for iid in failed_ids:
        failure_data = {
            "instance_id": iid,
            "question": questions_map.get(iid, "Unknown"),
            "generated_sql": "",
            "gold_sql": "",
            "csv_result": "",
            "gold_csv_result": ""
        }
        
        # Get Generated SQL
        sql_path = OLD_RESULTS_DIR / "sql" / f"{iid}.sql"
        if not sql_path.exists():
            sql_path = failed_dir / f"{iid}.sql"
            
        if sql_path.exists():
            with open(sql_path, "r", encoding="utf-8") as f:
                failure_data["generated_sql"] = f.read()

        # Get Gold SQL
        gold_sql_path = GOLD_SQL_DIR / f"{iid}.sql"
        if gold_sql_path.exists():
            with open(gold_sql_path, "r", encoding="utf-8") as f:
                failure_data["gold_sql"] = f.read()

        # Get Generated CSV Result
        csv_path = OLD_RESULTS_DIR / "csv" / f"{iid}.csv"
        if not csv_path.exists():
            csv_path = failed_dir / f"{iid}.csv"
            
        if csv_path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                failure_data["csv_result"] = f.read()

        # Get Gold CSV Result
        gold_csv_path = GOLD_CSV_DIR / f"{iid}.csv"
        # Try suffix _a (common in Spider-2 gold sets)
        if not gold_csv_path.exists():
            gold_csv_path = GOLD_CSV_DIR / f"{iid}_a.csv"
            
        if gold_csv_path.exists():
            with open(gold_csv_path, "r", encoding="utf-8") as f:
                failure_data["gold_csv_result"] = f.read()
        
        failures.append(failure_data)

    # Write to JSON
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = JSON_LOGS_DIR / f"failures_detailed_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)
        
    print(f"Saved {len(failures)} failures to {output_file}")

if __name__ == "__main__":
    collect_failures()
