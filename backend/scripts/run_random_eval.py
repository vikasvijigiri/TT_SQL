import json
import os
import random
import shutil
import argparse
import pandas as pd
from pathlib import Path
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app.core.config import INPUT_DIR, GOLD_DIR, RESULTS_DIR, get_db_path

# Preserve stdout/stderr before importing evaluate.py which redirects to TeeOutput
old_stdout = sys.stdout
old_stderr = sys.stderr
# sys.path.append(str(GOLD_DIR)) # no longer needed
from backend.resources.gold.evaluate import load_jsonl_to_dict, evaluate_single_exec_result_instance
sys.stdout = old_stdout
sys.stderr = old_stderr

def _worker_run_instance(inst_data):
    """Top-level worker function for parallel execution."""
    # Re-import inside worker process
    from backend.app.core.orchestrator import SemanticDINOrchestrator
    from backend.app.utils.logger import logger
    
    instance_id = inst_data['instance_id']
    db_name = inst_data['db']
    question = inst_data['question']
    
    try:
        db_path = get_db_path(db_name)
        orchestrator = SemanticDINOrchestrator(db_directory=db_path, db_name=db_name)
        
        save_dir = os.path.join(str(RESULTS_DIR), db_name.upper())
        os.makedirs(save_dir, exist_ok=True)
        md_path = os.path.join(save_dir, f"{instance_id}.md")
        logger.start_live_task_log(md_path)
        
        success_msg = orchestrator.execute_query(user_query=question, instance_id=instance_id)
        logger.stop_live_task_log()
        
        csv_path = Path(save_dir) / f"{instance_id}.csv"
        sql_path = Path(save_dir) / f"{instance_id}.sql"
        
        if not csv_path.exists() or os.path.getsize(csv_path) <= 1:
            return {"instance_id": instance_id, "db": db_name, "status": "EMPTY", "csv_path": None, "sql": ""}
            
        sql_content = sql_path.read_text(encoding='utf-8') if sql_path.exists() else ""
        return {"instance_id": instance_id, "db": db_name, "status": "SUCCESS", "csv_path": str(csv_path), "sql": sql_content}
    except Exception as e:
        return {"instance_id": instance_id, "db": db_name, "status": f"ERROR: {e}", "csv_path": None, "sql": ""}

def main():
    parser = argparse.ArgumentParser(description="Run parallel random evaluation against Spider2-Lite Gold.")
    parser.add_argument("--n", type=int, default=5, help="Number of random instances to run")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel worker processes")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    input_file = INPUT_DIR / "spider2-lite-snowflake.jsonl"
    all_instances = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            all_instances.append(json.loads(line))
            
    all_ids = [inst['instance_id'] for inst in all_instances]
    selected_instances = random.sample(all_instances, min(args.n, len(all_instances)))
    
    print(f"\n{'='*80}")
    print(f">>> STARTING PARALLEL RANDOM EVALUATION: {len(selected_instances)} INSTANCES ({args.workers} WORKERS)")
    print(f"Selected IDs: {[inst['instance_id'] for inst in selected_instances]}")
    print(f"{'='*80}\n")
    
    # Execution Phase
    completed_runs = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_inst = {executor.submit(_worker_run_instance, inst): inst for inst in selected_instances}
        for future in as_completed(future_to_inst):
            inst = future_to_inst[future]
            try:
                result = future.result()
                completed_runs.append(result)
                print(f"[WORKER DONE] {result['instance_id']} ({result['db']}) -> {result['status']}")
            except Exception as exc:
                print(f"[WORKER CRASH] {inst['instance_id']} generated an exception: {exc}")
                completed_runs.append({"instance_id": inst['instance_id'], "db": inst['db'], "status": f"CRASH: {exc}", "csv_path": None, "sql": ""})
                
    # Evaluation Phase against Gold
    print(f"\n{'='*80}")
    print(">>> GATHERING SUBMISSIONS & EVALUATING AGAINST GOLD STANDARD")
    print(f"{'='*80}\n")
    
    eval_submission_dir = RESULTS_DIR / "eval_submission"
    if eval_submission_dir.exists():
        shutil.rmtree(eval_submission_dir)
    eval_submission_dir.mkdir(parents=True, exist_ok=True)
    
    for r in completed_runs:
        if r['csv_path'] and os.path.exists(r['csv_path']):
            dest = eval_submission_dir / f"{r['instance_id']}.csv"
            shutil.copy2(r['csv_path'], dest)
            
    eval_standards = load_jsonl_to_dict(str(GOLD_DIR / "spider2lite_eval.jsonl"))
    gold_exec_dir = str(GOLD_DIR / "exec_result")
    
    eval_reports = []
    correct_count = 0
    
    for r in completed_runs:
        iid = r['instance_id']
        db_name = r['db']
        status = r['status']
        sql = r['sql']
        
        if status != "SUCCESS" or not r['csv_path']:
            eval_reports.append({
                "id": iid, "db": db_name, "score": 0, "status": status, "diagnostic": "Execution failed or empty result."
            })
            continue
            
        eval_res = evaluate_single_exec_result_instance(
            instance_id=iid,
            eval_standard_dict=eval_standards,
            pred_result_dir=str(eval_submission_dir),
            gold_result_dir=gold_exec_dir
        )
        
        score = eval_res.get("score", 0)
        err_info = eval_res.get("error_info")
        if score == 1:
            correct_count += 1
            diag = "PASS (Bit-for-Bit match with Gold Standard)"
        else:
            diag = f"FAIL (Mismatch with Gold Standard: {err_info})"
            
        eval_reports.append({
            "id": iid, "db": db_name, "score": score, "status": "EVALUATED", "diagnostic": diag, "sql": sql
        })

    print(f"\n{'='*80}")
    print(f"              FINAL BENCHMARK EVALUATION SUMMARY ({len(eval_reports)} INSTANCES)")
    print(f"{'='*80}")
    
    for rep in sorted(eval_reports, key=lambda x: x['id']):
        sc_str = "PASS [1.0]" if rep['score'] == 1 else "FAIL [0.0]"
        print(f"-> {rep['id']:<10} | DB: {rep['db']:<18} | Result: {sc_str:<10} | Notes: {rep['diagnostic']}")
        if rep['score'] == 0 and rep.get('sql'):
            print(f"   [Failed Query Preview]: {rep['sql'][:150]}...")
            
    acc = (correct_count / len(eval_reports)) * 100 if eval_reports else 0.0
    print(f"\nTotal Evaluated: {len(eval_reports)}")
    print(f"Total Correct:   {correct_count}")
    print(f"Final Accuracy:  {acc:.2f}%\n")

if __name__ == "__main__":
    main()
