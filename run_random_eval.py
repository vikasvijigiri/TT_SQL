import json
import os
import random
import pandas as pd
import math
from pathlib import Path
import sys

# Add current dir to path to import src
sys.path.append(os.getcwd())

def normalize(value):
    if pd.isna(value):
        return 0
    return value

def vectors_match(v1, v2, tol=1e-2, ignore_order_=False):
    v1 = [normalize(x) for x in v1]
    v2 = [normalize(x) for x in v2]
    if ignore_order_:
        v1 = sorted(v1, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))
        v2 = sorted(v2, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))
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

def compare_pandas_table(pred: pd.DataFrame, gold: pd.DataFrame, condition_cols=None, ignore_order: bool = False) -> int:
    if condition_cols:
        gold_cols = gold.iloc[:, condition_cols]
    else:
        gold_cols = gold
    pred_cols = pred
    
    t_gold_list = gold_cols.transpose().values.tolist()
    t_pred_list = pred_cols.transpose().values.tolist()
    
    score = 1
    for gold_vector in t_gold_list:
        if not any(vectors_match(gold_vector, pred_vector, ignore_order_=ignore_order) for pred_vector in t_pred_list):
            score = 0
            break
    return score

def get_db_path(db_name: str) -> str:
    base_db_dir = "resources/databases/snowflake"
    db_root = os.path.join(base_db_dir, db_name)
    if not os.path.exists(db_root):
        raise ValueError(f"Database directory not found: {db_root}")
    for root, dirs, files in os.walk(db_root):
        if any(f.endswith('.json') for f in files):
            return root
    raise ValueError(f"No JSON metadata files found in {db_root}")

def run_random_eval(n=5):
    input_file = "input_data/spider2-lite-snowflake.jsonl"
    with open(input_file, 'r', encoding='utf-8') as f:
        all_instances = [json.loads(line) for line in f]
    
    all_ids = [inst['instance_id'] for inst in all_instances]
    selected_ids = random.sample(all_ids, n)
    
    results = []
    
    gold_jsonl = "gold/spider2lite_eval.jsonl"
    eval_standards = {}
    with open(gold_jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            eval_standards[item['instance_id']] = item

    from src.core.orchestrator import SemanticDINOrchestrator
    from src.utils.logger import logger

    for instance_id in selected_ids:
        print(f"\n>>> RUNNING {instance_id}")
        inst_data = next(inst for inst in all_instances if inst['instance_id'] == instance_id)
        
        try:
            db_path = get_db_path(inst_data['db'])
            orchestrator = SemanticDINOrchestrator(db_directory=db_path, db_name=inst_data['db'])
            
            # Start logging to markdown as run_batch does
            save_dir = os.path.join("results", inst_data['db'])
            os.makedirs(save_dir, exist_ok=True)
            md_path = os.path.join(save_dir, f"{instance_id}.md")
            logger.start_live_task_log(md_path)
            
            success_msg = orchestrator.execute_query(user_query=inst_data['question'], instance_id=instance_id)
            
            logger.stop_live_task_log()
            
            # Find produced CSV
            csv_path = Path(f"results/{inst_data['db']}/{instance_id}.csv")
            if not csv_path.exists() or os.path.getsize(csv_path) <= 1:
                results.append({"id": instance_id, "status": "EMPTY", "score": 0})
                continue
            
            pred_df = pd.read_csv(csv_path)
            
            # Find Gold CSV(s)
            gold_dir = Path("gold/exec_result")
            # Try matching with original instance_id, and with/without sf_ prefix
            gold_files = list(gold_dir.glob(f"{instance_id}*.csv"))
            if not gold_files:
                alt_id = instance_id.replace("sf_", "") if instance_id.startswith("sf_") else f"sf_{instance_id}"
                gold_files = list(gold_dir.glob(f"{alt_id}*.csv"))
            
            if not gold_files:
                results.append({"id": instance_id, "status": f"SKIP (No Gold CSV)", "score": 0})
                continue
            
            # Compare
            standard = eval_standards.get(instance_id, {})
            cond_cols = standard.get("condition_cols")
            ignore_order = standard.get("ignore_order", False)
            
            max_score = 0
            for gold_file in gold_files:
                gold_df = pd.read_csv(gold_file)
                try:
                    score = compare_pandas_table(pred_df, gold_df, cond_cols, ignore_order)
                    max_score = max(max_score, score)
                except Exception as e:
                    print(f"Comparison error for {gold_file}: {e}")
            
            results.append({
                "id": instance_id, 
                "status": "PASS" if max_score == 1 else "FAIL (Mismatch)", 
                "score": max_score,
                "rows": len(pred_df)
            })
            
        except Exception as e:
            print(f"Error running {instance_id}: {e}")
            results.append({"id": instance_id, "status": f"ERROR: {str(e)[:40]}", "score": 0})

    print("\n" + "="*50)
    print("RANDOM EVALUATION SUMMARY")
    print("="*50)
    for res in results:
        print(f"{res['id']:<15} | {res['status']:<25} | Score: {res.get('score', 0)}")
    print("="*50)

if __name__ == "__main__":
    run_random_eval(5)
