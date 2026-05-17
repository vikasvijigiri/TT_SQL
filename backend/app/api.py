import os
import sys
import json
import re
import math
import warnings
import pandas as pd
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import subprocess
import time
from datetime import datetime
from functools import lru_cache

# Suppress Python 3.14 / LangChain / Pydantic compatibility warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")
warnings.filterwarnings("ignore", message=".*Pydantic.*")

import yaml
from backend.app.core.config import RESULTS_DIR, DATABASES_DIR, INPUT_DIR, GOLD_DIR, PROMPTS_DIR, MEMORY_DIR, CONFIG_DIR

# Track active background tasks to prevent UI flickering
RUNNING_TASKS = set()
GLOBAL_AUDIT_RUNNING = False

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

@lru_cache(maxsize=1024)
def _cached_gold_eval(instance_id: str, pred_csv_path_str: str, mtime: float) -> Optional[str]:
    gold_result_dir = GOLD_DIR / "exec_result"
    pred_csv_path = Path(pred_csv_path_str)
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
        return None

def evaluate_against_gold(instance_id: str, pred_csv_path: Path) -> Optional[str]:
    """Returns 'gold_pass', 'gold_fail', or None if gold not available."""
    if not pred_csv_path.exists():
        return None
    try:
        mtime = pred_csv_path.stat().st_mtime
        return _cached_gold_eval(instance_id, str(pred_csv_path), mtime)
    except:
        return None

@lru_cache(maxsize=1024)
def _cached_read_csv_info(csv_path_str: str, mtime: float) -> tuple[bool, int]:
    try:
        df = pd.read_csv(csv_path_str)
        return df.empty, len(df)
    except:
        return True, 0

def get_csv_info(csv_path: Path) -> tuple[bool, int]:
    if not csv_path.exists():
        return True, 0
    try:
        return _cached_read_csv_info(str(csv_path), csv_path.stat().st_mtime)
    except:
        return True, 0

app = FastAPI(title="Text2SQL Dashboard API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@lru_cache(maxsize=1024)
def _cached_parse_md_log(file_path_str: str, mtime: float) -> Dict[str, Any]:
    content = ""
    try:
        with open(file_path_str, "r", encoding="utf-8") as f:
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

def parse_md_log(file_path: Path) -> Dict[str, Any]:
    """Extracts metadata from an execution log file with caching."""
    if not file_path.exists():
        return {}
    try:
        return _cached_parse_md_log(str(file_path), file_path.stat().st_mtime)
    except:
        return {}

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
    error_count = 0
    gold_pass_count = 0
    complexity_counts = {"linear_logic": 0, "relational_complexity": 0, "forensic_depth": 0, "unknown": 0}
    
    if RESULTS_DIR.exists():
        for md_file in RESULTS_DIR.glob("**/*.md"):
            instance_id = md_file.stem
            csv_file = md_file.parent / f"{instance_id}.csv"
            data = parse_md_log(md_file)
            total_instances += 1
            
            if data.get("error"):
                error_count += 1
            elif csv_file.exists():
                is_empty, _ = get_csv_info(csv_file)
                if not is_empty:
                    success_count += 1
                    if evaluate_against_gold(instance_id, csv_file) == "gold_pass":
                        gold_pass_count += 1
            
            total_latency += data.get("latency", 0)
            comp = data.get("complexity", "unknown")
            complexity_counts[comp] = complexity_counts.get(comp, 0) + 1

    avg_latency = total_latency / total_instances if total_instances > 0 else 0
    est_tokens = total_instances * 22500 # ~4500 per agent * 5 agents
    avg_tokens_per_agent = 4500 if total_instances > 0 else 0
    
    return {
        "total_processed": total_instances,
        "errored_count": error_count,
        "succeeded_count": success_count,
        "gold_succeeded_count": gold_pass_count,
        "gold_accuracy": f"{(gold_pass_count/total_instances*100):.1f}%" if total_instances > 0 else "0.0%",
        "avg_latency": f"{avg_latency:.1f}s" if avg_latency > 0 else "0.0s",
        "avg_tokens_per_agent": f"{avg_tokens_per_agent:,} tokens",
        "total_tokens": f"{est_tokens/1000000:.1f}M" if est_tokens > 1000000 else f"{est_tokens/1000:.0f}K",
        "llm_calls": total_instances * 5,
        "complexity_distribution": {
            "easy": complexity_counts.get("linear_logic", 0),
            "medium": complexity_counts.get("relational_complexity", 0),
            "complex": complexity_counts.get("forensic_depth", 0)
        }
    }

from backend.app.services.semantic_engine import SemanticContextEngine

@lru_cache(maxsize=128)
def get_db_metadata_stats(db_dir_path: str):
    try:
        engine = SemanticContextEngine(db_dir_path, silent=True)
        schema_str = engine.format_for_prompt(include_samples=True)
        tokens = len(schema_str) // 4
        tables_count = len(engine.context.tables) if engine.context else 0
        return tokens, tables_count
    except Exception as e:
        return 0, 0

@app.get("/api/databases")
async def get_databases():
    """Returns list of databases, their token density, and execution status."""
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
                            is_empty, _ = get_csv_info(csv_file)
                            if is_empty:
                                empty_count += 1
                            else:
                                success_count += 1
                        else:
                            empty_count += 1
                
                total_questions = input_counts.get(db_name.strip().upper(), 0)
                processed = success_count + error_count + empty_count
                
                # Calculate schema token density and table count with caching
                tokens, tables_count = get_db_metadata_stats(str(db_dir))
                
                databases.append({
                    "name": db_name,
                    "status": "completed" if processed >= total_questions and total_questions > 0 else "pending",
                    "results_count": success_count,
                    "error_count": error_count,
                    "empty_count": empty_count,
                    "total_questions": total_questions,
                    "tokens": tokens,
                    "tables_count": tables_count
                })
    return sorted(databases, key=lambda x: x["results_count"] + x["error_count"], reverse=True)

@app.get("/api/results/recent")
async def get_recent_results(limit: int = 10):
    """Returns the most recent execution results across all databases."""
    recent_runs = []
    
    if not RESULTS_DIR.exists():
        return []
        
    # Walk through all subdirectories in RESULTS_DIR
    all_md_files = list(RESULTS_DIR.glob("**/*.md"))
    # Sort by modification time descending
    all_md_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    for md_file in all_md_files[:limit]:
        instance_id = md_file.stem
        db_name = md_file.parent.name
        csv_file = md_file.parent / f"{instance_id}.csv"
        
        log_data = parse_md_log(md_file)
        status = "error" if log_data.get("error") else "pending"
        gold_status = None
        
        if csv_file.exists():
            is_empty, _ = get_csv_info(csv_file)
            status = "success" if not is_empty else "empty"
            gold_status = evaluate_against_gold(instance_id, csv_file)
        
        recent_runs.append({
            "id": instance_id,
            "db": db_name,
            "status": status,
            "gold_status": gold_status,
            "timestamp": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
        })
        
    return recent_runs

@app.get("/api/results/all")
async def get_all_results():
    """Returns all execution results across all databases for metric breakdown navigation."""
    all_runs = []
    if not RESULTS_DIR.exists():
        return []
        
    for md_file in RESULTS_DIR.glob("**/*.md"):
        instance_id = md_file.stem
        db_name = md_file.parent.name
        csv_file = md_file.parent / f"{instance_id}.csv"
        
        log_data = parse_md_log(md_file)
        status = "error" if log_data.get("error") else "pending"
        gold_status = None
        
        if csv_file.exists():
            is_empty, _ = get_csv_info(csv_file)
            status = "success" if not is_empty else "empty"
            gold_status = evaluate_against_gold(instance_id, csv_file)
        elif log_data.get("success"):
            status = "empty"
        
        all_runs.append({
            "id": instance_id,
            "db": db_name,
            "status": status,
            "gold_status": gold_status,
            "latency": log_data.get("latency", 0),
            "complexity": log_data.get("complexity", "unknown"),
            "timestamp": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
        })
        
    all_runs.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_runs

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
                                is_empty, rows = get_csv_info(csv_file)
                                status = "success" if not is_empty else "empty"
                                row_count = rows
                                gold_status = evaluate_against_gold(instance_id, csv_file)
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
            subprocess.run([sys.executable, "backend/scripts/run_batch.py", "--instance", clean_id], 
                           env={**os.environ, "PYTHONPATH": "."})
        finally:
            RUNNING_TASKS.discard(clean_id)
    
    background_tasks.add_task(run_script)
    return {"message": f"Pipeline started for instance {clean_id}"}

@app.post("/api/run/{db_name}")
async def run_pipeline(db_name: str, background_tasks: BackgroundTasks, workers: int = 4):
    """Triggers the run_batch script for a DB."""
    def run_script():
        subprocess.run([sys.executable, "backend/scripts/run_batch.py", "--db", db_name, "--workers", str(workers)], 
                       env={**os.environ, "PYTHONPATH": "."})
    
    background_tasks.add_task(run_script)
    return {"message": f"Pipeline started for {db_name} with {workers} workers"}

@app.post("/api/run_all")
async def run_all_snowflake(background_tasks: BackgroundTasks, workers: int = 4):
    """Triggers the run_batch script for all snowflake instances across the entire benchmark."""
    def run_script():
        subprocess.run([sys.executable, "backend/scripts/run_batch.py", "--n", "0", "--workers", str(workers)], 
                       env={**os.environ, "PYTHONPATH": "."})
    
    background_tasks.add_task(run_script)
    return {"message": f"Global Snowflake benchmark started with {workers} concurrent workers"}

@app.post("/api/evaluate/all")
async def trigger_global_audit(background_tasks: BackgroundTasks):
    """Triggers the evaluation script for all result directories."""
    global GLOBAL_AUDIT_RUNNING
    if GLOBAL_AUDIT_RUNNING:
        return {"message": "Global audit already in progress."}
        
    GLOBAL_AUDIT_RUNNING = True
    
    def run_eval():
        global GLOBAL_AUDIT_RUNNING
        try:
            subprocess.run([sys.executable, "backend/resources/gold/evaluate.py", "--mode", "exec_result", 
                           "--result_dir", str(RESULTS_DIR), "--gold_dir", str(GOLD_DIR)], 
                           env={**os.environ, "PYTHONPATH": "."})
        finally:
            GLOBAL_AUDIT_RUNNING = False
            
    background_tasks.add_task(run_eval)
    return {"message": "Global gold-standard audit initiated."}

@app.get("/api/evaluate/status")
async def get_audit_status():
    return {"running": GLOBAL_AUDIT_RUNNING}

class PromptUpdateRequest(BaseModel):
    content: str

@app.get("/api/settings")
async def get_system_settings():
    params_file = CONFIG_DIR / "system_params.yaml"
    if params_file.exists():
        with open(params_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

@app.post("/api/settings")
async def update_system_settings(req: dict):
    params_file = CONFIG_DIR / "system_params.yaml"
    with open(params_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(req, f)
    return {"message": "Settings updated successfully", "settings": req}

class TopologyRequest(BaseModel):
    nodes: List[dict] = []
    connections: List[dict] = []

@app.get("/api/topology")
async def get_workflow_topology():
    topo_file = CONFIG_DIR / "topology.json"
    if topo_file.exists():
        try:
            with open(topo_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"nodes": [], "connections": []}
    return {"nodes": [], "connections": []}

@app.post("/api/topology")
async def update_workflow_topology(req: TopologyRequest):
    topo_file = CONFIG_DIR / "topology.json"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(topo_file, "w", encoding="utf-8") as f:
        json.dump(req.dict(), f, indent=2)
    return {"message": "Topology saved successfully"}

@app.get("/api/prompts")
async def get_system_prompts():
    prompts = []
    # Scan PROMPTS_DIR
    if PROMPTS_DIR.exists():
        for p in sorted(PROMPTS_DIR.glob("*.yaml")):
            with open(p, "r", encoding="utf-8") as f:
                prompts.append({
                    "id": p.name,
                    "category": "Pipeline Agent Prompts",
                    "path": str(p),
                    "content": f.read()
                })
    # Scan MEMORY_DIR / reasoning
    reasoning_dir = MEMORY_DIR / "reasoning"
    if reasoning_dir.exists():
        for p in sorted(reasoning_dir.glob("*.yaml")):
            with open(p, "r", encoding="utf-8") as f:
                prompts.append({
                    "id": p.name,
                    "category": "Reasoning Protocols",
                    "path": str(p),
                    "content": f.read()
                })
    return prompts

@app.post("/api/prompts/{filename}")
async def update_prompt_content(filename: str, req: PromptUpdateRequest):
    target_path = None
    if (PROMPTS_DIR / filename).exists():
        target_path = PROMPTS_DIR / filename
    elif (MEMORY_DIR / "reasoning" / filename).exists():
        target_path = MEMORY_DIR / "reasoning" / filename
        
    if not target_path:
        return {"error": f"Prompt file not found: {filename}"}
        
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(req.content)
    return {"message": f"Successfully updated {filename}"}

class CopilotAgentRequest(BaseModel):
    user_prompt: str
    active_agents: Optional[List[str]] = []

@app.post("/api/copilot/agent")
async def copilot_create_agent(req: CopilotAgentRequest):
    from backend.app.utils.llm import LLMClient
    from backend.app.utils.logger import logger
    
    system_prompt = """You are SpiderDIN AI Copilot, an elite AI Agent Architect.
The user wants to spawn a new agentic processor or modify an existing prompt protocol in the workflow.
Analyze their request and generate a complete, professional agent specification.

You MUST return strictly valid JSON matching this exact structure:
{
  "title": "Agent Title (e.g., Financial Continuity Auditor)",
  "category": "One of: Discovery, Planning, Execution, Correction, Auditing, Memory, Custom",
  "desc": "Short 1-2 sentence description of what the agent probes, calculates, or validates.",
  "targetFile": "valid_filename.yaml (must end with .yaml)",
  "content": "# System Prompt Protocol for Agent\\n# Category: ...\\n\\n# OBJECTIVE:\\n# Validate mathematical and cross-table continuity...\\n\\n# REASONING RULES:\\n..."
}
Do NOT include markdown code fences or explanatory text outside the JSON block."""

    client = LLMClient(temperature=0.2)
    try:
        logger.info(f"AI Copilot request received: '{req.user_prompt}'")
        data = client.generate_json(system_prompt, req.user_prompt)
        if not data:
            return {"error": "Failed to generate valid JSON agent specification from LLM."}
            
        target_file = data.get("targetFile", f"agent_{int(time.time())}.yaml")
        if not target_file.endswith(".yaml"):
            target_file += ".yaml"
            
        content = data.get("content", f"# Prompt protocol for {data.get('title', 'Agent')}\n")
        
        # Ensure PROMPTS_DIR exists
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        file_path = PROMPTS_DIR / target_file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        agent_node = {
            "id": f"agent_{int(time.time())}",
            "title": data.get("title", "AI Architected Agent"),
            "category": data.get("category", "Custom"),
            "desc": data.get("desc", "Dynamically architected by AI Copilot."),
            "targetFile": target_file,
            "isLoop": False
        }
        
        logger.info(f"Successfully generated agent: {agent_node['title']} ({target_file})")
        return {
            "status": "success",
            "agent": agent_node,
            "prompt": {
                "id": target_file,
                "category": f"{agent_node['category']} Protocol",
                "path": str(file_path),
                "content": content
            },
            "message": f"Successfully created agent '{agent_node['title']}' and saved protocol to {target_file}!"
        }
    except Exception as e:
        logger.error(f"Copilot agent creation failed: {str(e)}")
        return {"error": f"Internal LLM processing error: {str(e)}"}

class TestAgentRequest(BaseModel):
    agent_id: str
    prompt_file: str
    input_query: str
    context_data: Optional[str] = ""

@app.post("/api/test/agent")
async def test_agent_sandbox(req: TestAgentRequest):
    from backend.app.utils.llm import LLMClient
    from backend.app.utils.logger import logger
    start_t = time.time()
    
    target_path = None
    if (PROMPTS_DIR / req.prompt_file).exists():
        target_path = PROMPTS_DIR / req.prompt_file
    elif (MEMORY_DIR / "reasoning" / req.prompt_file).exists():
        target_path = MEMORY_DIR / "reasoning" / req.prompt_file
        
    if not target_path:
        prompt_content = f"# Prompt protocol for {req.agent_id}\n# Follow instructions precisely."
    else:
        with open(target_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()
            
    sys_prompt = f"""You are executing as the specialized AI Agent: {req.agent_id}.
Follow your prompt protocol strictly:
{prompt_content}

Your goal is to process the input precisely as instructed by your protocol."""

    user_prompt = f"""Primary Input / Question:
{req.input_query}

Supplementary Context / Linkage Metadata:
{req.context_data}"""

    client = LLMClient(temperature=0.0)
    try:
        logger.info(f"Executing Live Sandbox Test for agent {req.agent_id}")
        output = client.generate(sys_prompt, user_prompt)
        elapsed = round((time.time() - start_t) * 1000)
        
        return {
            "status": "success",
            "agent": req.agent_id,
            "output": output,
            "latency_ms": elapsed,
            "estimated_tokens": len(output) // 4 + len(sys_prompt) // 4
        }
    except Exception as e:
        logger.error(f"Sandbox test failed: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


