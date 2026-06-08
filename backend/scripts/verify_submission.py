import json
from pathlib import Path

OFFICIAL_DATASETS = [
    "agnews",
    "bookreview",
    "crmarenapro",
    "deps_dev_v1",
    "github_repos",
    "googlelocal",
    "music_brainz_20k",
    "pancancer_atlas",
    "patents",
    "stockindex",
    "stockmarket",
    "yelp",
]

DATASET_QUERY_COUNTS = {
    "agnews": 4,
    "bookreview": 3,
    "crmarenapro": 13,
    "deps_dev_v1": 2,
    "github_repos": 4,
    "googlelocal": 4,
    "music_brainz_20k": 3,
    "pancancer_atlas": 3,
    "patents": 3,
    "stockindex": 3,
    "stockmarket": 5,
    "yelp": 7,
}

def safe_str(s):
    return str(s).encode("ascii", errors="replace").decode("ascii")

def check_file(file_path):
    print("=" * 60)
    print(f"Checking file: {safe_str(file_path)}")
    print("=" * 60)
    
    path = Path(file_path)
    if not path.exists():
        print(f"[FAIL] File does not exist: {safe_str(path)}")
        return False
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[FAIL] Failed to parse JSON: {safe_str(e)}")
        return False
        
    print(f"[OK] Valid JSON format.")
    print(f"[OK] Total entries in array: {len(data)}")
    
    # Map to track runs: {(dataset, query): set(runs)}
    run_map = {}
    # Map to track empty answers: {(dataset, query, run): answer}
    empty_answers = []
    # Map to track answer snippets
    sample_answers = {}

    for idx, entry in enumerate(data):
        # Validate fields
        for field in ["dataset", "query", "run", "answer"]:
            if field not in entry:
                print(f"[FAIL] Entry at index {idx} is missing field '{field}': {safe_str(entry)}")
                return False
                
        dataset = entry["dataset"]
        query = entry["query"]
        run = entry["run"]
        answer = entry["answer"]
        
        key = (dataset, query)
        if key not in run_map:
            run_map[key] = set()
        run_map[key].add(run)
        
        if not answer or str(answer).strip() == "":
            empty_answers.append((dataset, query, run))
            
        if key not in sample_answers and answer:
            sample_answers[key] = str(answer)[:60] + "..." if len(str(answer)) > 60 else str(answer)

    # Now verify counts and runs
    errors = 0
    total_queries_expected = sum(DATASET_QUERY_COUNTS.values())
    total_runs_expected = total_queries_expected * 5
    
    print(f"Expected queries: {total_queries_expected}, Expected total runs: {total_runs_expected}")
    
    # Check if we have all datasets and queries
    table_rows = []
    for dataset in OFFICIAL_DATASETS:
        expected_queries = DATASET_QUERY_COUNTS[dataset]
        for q in range(1, expected_queries + 1):
            key = (dataset, q)
            if key not in run_map:
                print(f"[FAIL] Missing query: {safe_str(dataset)} Q{q}")
                errors += 1
                continue
                
            runs = run_map[key]
            expected_runs = {0, 1, 2, 3, 4}
            missing_runs = expected_runs - runs
            extra_runs = runs - expected_runs
            
            status = "OK"
            if missing_runs:
                status = f"MISSING {safe_str(missing_runs)}"
                errors += 1
            elif extra_runs:
                status = f"EXTRA {safe_str(extra_runs)}"
                errors += 1
                
            sample = sample_answers.get(key, "EMPTY")
            table_rows.append((dataset, q, len(runs), status, sample))

    print("\nDataset Query Verification Table:")
    print(f"{'Dataset':<18} | {'Query':<5} | {'Runs':<5} | {'Status':<12} | {'Sample Answer (Run 0)':<50}")
    print("-" * 100)
    for row in table_rows:
        line = f"{row[0]:<18} | {row[1]:<5} | {row[2]:<5} | {row[3]:<12} | {row[4]:<50}"
        print(safe_str(line))

    print("-" * 100)
    if empty_answers:
        print(f"[WARNING] Found {len(empty_answers)} runs with empty/blank answers.")
        # Group empty answers by dataset/query
        empty_groups = {}
        for db, q, r in empty_answers:
            k = (db, q)
            if k not in empty_groups:
                empty_groups[k] = []
            empty_groups[k].append(r)
        for k, runs in sorted(empty_groups.items()):
            print(f"  - {safe_str(k[0])} Q{k[1]}: empty in runs {safe_str(runs)}")
    else:
        print("[OK] All 270 runs have non-empty answers.")

    if errors == 0 and len(data) == total_runs_expected:
        print("\n[SUCCESS] Verification SUCCESS! All datasets, queries, and exactly 5 runs (0-4) are correctly populated.")
        return True
    else:
        print(f"\n[FAIL] Verification FAILED with {errors} structure errors.")
        return False

if __name__ == "__main__":
    import sys
    # Paths to verify
    sub_spiderdin = "C:/Users/VikasVijigiri/Documents/TT_SQL_V2/backend/results/dab/submission_spiderdin.json"
    sub_dab = "C:/Users/VikasVijigiri/Documents/DataAgentBench/submissions/tot_sql_safeguard.json"
    
    print("Starting verification checks...\n")
    check_file(sub_spiderdin)
    print("\n" + "="*80 + "\n")
    check_file(sub_dab)
