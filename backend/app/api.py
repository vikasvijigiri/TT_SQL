import os
import json
import re
import math
import warnings
import pandas as pd
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import List, Dict, Any, Optional
import subprocess
import time
from datetime import datetime
from functools import lru_cache

# Suppress Python 3.14 / LangChain / Pydantic compatibility warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")
warnings.filterwarnings("ignore", message=".*Pydantic.*")

from backend.app.core.config import RESULTS_DIR, DATABASES_DIR, INPUT_DIR, GOLD_DIR

# Track active background tasks to prevent UI flickering
RUNNING_TASKS = set()

# ---------------------------------------------------------------------------
# Gold Evaluation Helpers (mirrors evaluate.py logic, no Snowflake needed)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_eval_standards() -> dict:
    jsonl_path = GOLD_DIR / "spider2lite_eval.jsonl"
    standards = {}
    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line.strip())
                standards[item["instance_id"]] = item
    return standards

def get_eval_standards() -> dict:
    return _load_eval_standards()

def _normalize(value):
    if pd.isna(value):
        return 0
    return value

def _vectors_match(v1, v2, tol=1e-2, ignore_order=False):
    v1 = [_normalize(x) for x in v1]
    v2 = [_normalize(x) for x in v2]
    if ignore_order:
        key = lambda x: (x is None, str(x), isinstance(x, (int, float)))
        v1 = sorted(v1, key=key)
        v2 = sorted(v2, key=key)
    if len(v1) != len(v2):
        return False
    for a, b in zip(v1, v2):
        if pd.isna(a) and pd.isna(b):
            continue
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if not math.isclose(float(a), float(b), abs_tol=tol):
                return False
        elif str(a).strip().lower() != str(b).strip().lower():
            return False
    return True

def _compare_tables(pred: pd.DataFrame, gold: pd.DataFrame, condition_cols=None, ignore_order=False) -> int:
    if condition_cols:
        if not isinstance(condition_cols[0], list):
            condition_cols = [condition_cols]
        # Try each condition_cols variant, return 1 if any matches
        for cc in condition_cols:
            try:
                gold_subset = gold.iloc[:, cc]
            except IndexError:
                continue
            t_gold = gold_subset.transpose().values.tolist()
            t_pred = pred.transpose().values.tolist()
            score = 1
            for gv in t_gold:
                if not any(_vectors_match(gv, pv, ignore_order=ignore_order) for pv in t_pred):
                    score = 0
                    break
            if score == 1:
                return 1
        return 0
    else:
        t_gold = gold.transpose().values.tolist()
        t_pred = pred.transpose().values.tolist()
        for gv in t_gold:
            if not any(_vectors_match(gv, pv, ignore_order=ignore_order) for pv in t_pred):
                return 0
        return 1

def evaluate_against_gold(instance_id: str, pred_csv_path: Path) -> Optional[str]:
    """Returns 'gold_pass', 'gold_fail', or None if gold not available."""
    gold_result_dir = GOLD_DIR / "exec_result"
    if not gold_result_dir.exists() or not pred_csv_path.exists():
        return None
    try:
        standards = get_eval_standards()
        standard = standards.get(instance_id, {})
        condition_cols = standard.get("condition_cols")
        ignore_order = standard.get("ignore_order", False)

        # Find matching gold CSVs (e.g. sf_bq029_a.csv, sf_bq029_b.csv)
        pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")
        gold_paths = sorted([p for p in gold_result_dir.iterdir() if pattern.match(p.name)])
        if not gold_paths:
            return None

        pred_df = pd.read_csv(pred_csv_path)
        for gp in gold_paths:
            gold_df = pd.read_csv(gp)
            score = _compare_tables(pred_df, gold_df, condition_cols, ignore_order)
            if score == 1:
                return "gold_pass"
        return "gold_fail"
    except Exception as e:
        print(f"Gold eval error for {instance_id}: {e}")
        return None

app = FastAPI(title="Text2SQL Dashboard API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_md_log(file_path: Path) -> Dict[str, Any]:
    """Extracts metadata from an execution log file."""
    content = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except: return {}

    latency_match = re.search(r"Latency:\s*(\d+\.\d+)s", content)
    complexity_match = re.search(r'"complexity":\s*"(\w+)"', content)
    
    # Only mark as error if it's the LAST thing that happened or if no success marker exists
    has_error = "ERROR" in content or "Traceback" in content
    has_success = "SUCCESS" in content or "Final SQL" in content
    
    return {
        "latency": float(latency_match.group(1)) if latency_match else 0,
        "complexity": complexity_match.group(1) if complexity_match else "unknown",
        "success": has_success,
        "error": has_error and not has_success
    }

def get_input_counts() -> Dict[str, int]:
    """Counts questions per DB from the input JSONL file."""
    counts = {}
    input_file = INPUT_DIR / "spider2-lite-snowflake.jsonl"
    if input_file.exists():
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    db = data.get("db", "UNKNOWN").strip().upper()
                    counts[db] = counts.get(db, 0) + 1
        except Exception as e:
            print(f"Error reading input counts: {e}")
    return counts

@app.get("/api/metrics")
async def get_metrics():
    """Aggregates real metrics across all results."""
    total_latency = 0
    total_instances = 0
    success_count = 0
    complexity_counts = {"easy": 0, "non_nested_complex": 0, "nested_complex": 0, "unknown": 0}
    
    if RESULTS_DIR.exists():
        for md_file in RESULTS_DIR.glob("**/*.md"):
            data = parse_md_log(md_file)
            total_instances += 1
            if data.get("success"):
                success_count += 1
            total_latency += data.get("latency", 0)
            comp = data.get("complexity", "unknown")
            complexity_counts[comp] = complexity_counts.get(comp, 0) + 1

    avg_latency = total_latency / total_instances if total_instances > 0 else 0
    est_tokens = total_instances * 15000 
    
    return {
        "total_instances": total_instances,
        "success_rate": f"{(success_count/total_instances*100):.1f}%" if total_instances > 0 else "0%",
        "avg_latency": f"{avg_latency:.1f}s" if avg_latency > 0 else "N/A",
        "total_tokens": f"{est_tokens/1000000:.1f}M" if est_tokens > 1000000 else f"{est_tokens/1000:.0f}K",
        "llm_calls": total_instances * 5,
        "complexity_distribution": {
            "easy": complexity_counts["easy"],
            "medium": complexity_counts["non_nested_complex"],
            "complex": complexity_counts["nested_complex"]
        }
    }

@app.get("/api/databases")
async def get_databases():
    """Returns list of databases and their execution status."""
    databases = []
    input_counts = get_input_counts()
    
    sf_db_dir = DATABASES_DIR / "snowflake"
    if sf_db_dir.exists():
        for db_dir in sf_db_dir.iterdir():
            if db_dir.is_dir():
                db_name = db_dir.name
                res_dir = RESULTS_DIR / db_name
                
                success_count = 0
                error_count = 0
                empty_count = 0
                
                if res_dir.exists():
                    for md_file in res_dir.glob("*.md"):
                        log_data = parse_md_log(md_file)
                        csv_file = res_dir / f"{md_file.stem}.csv"
                        
                        if log_data.get("error"):
                            error_count += 1
                        elif csv_file.exists():
                            try:
                                df = pd.read_csv(csv_file)
                                if df.empty:
                                    empty_count += 1
                                else:
                                    success_count += 1
                            except:
                                error_count += 1
                        else:
                            # Log exists but no CSV and no explicit error log? Mark as failed execution
                            empty_count += 1
                
                total_questions = input_counts.get(db_name.strip().upper(), 0)
                processed = success_count + error_count + empty_count
                
                databases.append({
                    "name": db_name,
                    "status": "completed" if processed >= total_questions and total_questions > 0 else "pending",
                    "results_count": success_count,
                    "error_count": error_count,
                    "empty_count": empty_count,
                    "total_questions": total_questions
                })
    return sorted(databases, key=lambda x: x["results_count"] + x["error_count"], reverse=True)

@app.get("/api/results/{db_name}")
async def get_db_results(db_name: str):
    """Returns detailed results and questions for all instances in a specific database."""
    results = []
    db_name_upper = db_name.strip().upper()
    res_dir = RESULTS_DIR / db_name_upper
    
    # First, get all instances from the jsonl file for this DB
    input_file = INPUT_DIR / "spider2-lite-snowflake.jsonl"
    if input_file.exists():
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    if data.get("db", "").strip().upper() == db_name_upper:
                        instance_id = data.get("instance_id")
                        question = data.get("question", "")
                        
                        # Now check if it has been processed
                        status = "pending"
                        row_count = 0
                        complexity = "unclassified"
                        log_path = ""
                        gold_status = None
                        
                        md_file = res_dir / f"{instance_id}.md"
                        csv_file = res_dir / f"{instance_id}.csv"
                        
                        # PRIORITY 1: Check if the task is actively running in the background
                        clean_id = instance_id.strip()
                        if clean_id in RUNNING_TASKS:
                            status = "running"
                        # PRIORITY 2: Check for existing artifacts
                        elif md_file.exists():
                            log_path = str(md_file)
                            log_data = parse_md_log(md_file)
                            complexity = log_data.get("complexity", "unknown")
                            
                            # Prioritize CSV existence for final status
                            if csv_file.exists():
                                try:
                                    df = pd.read_csv(csv_file)
                                    status = "success" if not df.empty else "empty"
                                    row_count = len(df)
                                    gold_status = evaluate_against_gold(instance_id, csv_file)
                                except:
                                    status = "error"
                            elif log_data.get("error"):
                                status = "error"
                            elif log_data.get("success"):
                                status = "empty"
                                    
                        results.append({
                            "id": instance_id,
                            "question": question,
                            "status": status,
                            "gold_status": gold_status,
                            "complexity": complexity,
                            "rows": row_count,
                            "log_path": log_path
                        })
        except Exception as e:
            print(f"Error reading instances: {e}")
            
    return results

@app.get("/api/details/{db_name}/{instance_id}")
async def get_instance_details(db_name: str, instance_id: str):
    """Returns the raw log, extracted SQL, and CSV data for a specific instance."""
    db_name_upper = db_name.strip().upper()
    res_dir = RESULTS_DIR / db_name_upper
    
    md_file = res_dir / f"{instance_id}.md"
    csv_file = res_dir / f"{instance_id}.csv"
    sql_file = res_dir / f"{instance_id}.sql"
    
    log_content = "Log file not found."
    sql_content = "SQL file not found."
    csv_headers = []
    csv_data = []
    executed_at = None
    
    if sql_file.exists():
        try:
            with open(sql_file, "r", encoding="utf-8", errors="replace") as f:
                sql_content = f.read().strip()
        except Exception as e:
            sql_content = f"Error reading SQL file: {e}"
            
    if md_file.exists():
        try:
            executed_at = datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
            with open(md_file, "r", encoding="utf-8", errors="replace") as f:
                log_content = f.read()
                
            # If the log contains multiple runs (since it appends), extract only the last run
            marker = "--- EXECUTION STARTED AT"
            if marker in log_content:
                parts = log_content.split(marker)
                if len(parts) > 1:
                    log_content = marker + parts[-1]
                    
            # Fallback for SQL if the .sql file didn't exist
            if not sql_file.exists():
                sql_match = re.search(r"```sql\n(.*?)\n```", log_content, re.DOTALL)
                if sql_match:
                    sql_content = sql_match.group(1).strip()
        except Exception as e:
            log_content = f"Error reading log: {e}"
            
    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            csv_headers = df.columns.tolist()
            # Replace NaNs with None for valid JSON serialization
            df = df.where(pd.notnull(df), None)
            # Limit to 100 rows for UI safety
            df = df.head(100)
            csv_data = df.to_dict(orient="records")
        except Exception as e:
            csv_data = [{"Error": f"Could not parse CSV: {e}"}]
            csv_headers = ["Error"]
            
    return {
        "log_content": log_content,
        "sql_content": sql_content,
        "csv_headers": csv_headers,
        "csv_data": csv_data,
        "executed_at": executed_at
    }

@app.post("/api/run_instance/{instance_id}")
async def run_single_instance(instance_id: str, background_tasks: BackgroundTasks):
    """Triggers the run_batch script for a single instance."""
    clean_id = instance_id.strip()
    # Mark as running IMMEDIATELY before sending response
    RUNNING_TASKS.add(clean_id)
    
    def run_script():
        try:
            subprocess.run(["python", "backend/scripts/run_batch.py", "--instance", clean_id], 
                           env={**os.environ, "PYTHONPATH": "."})
        finally:
            RUNNING_TASKS.discard(clean_id)
    
    background_tasks.add_task(run_script)
    return {"message": f"Pipeline started for instance {clean_id}"}

@app.post("/api/run/{db_name}")
async def run_pipeline(db_name: str, background_tasks: BackgroundTasks, workers: int = 4):
    """Triggers the run_batch script for a DB."""
    def run_script():
        subprocess.run(["python", "backend/scripts/run_batch.py", "--db", db_name, "--workers", str(workers)], 
                       env={**os.environ, "PYTHONPATH": "."})
    
    background_tasks.add_task(run_script)
    return {"message": f"Pipeline started for {db_name} with {workers} workers"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
