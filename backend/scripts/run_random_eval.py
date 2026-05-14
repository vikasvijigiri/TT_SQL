import json
import os
import random
import pandas as pd
import math
from pathlib import Path
import sys

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app.core.config import INPUT_DIR, GOLD_DIR, get_db_path

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
    
    if len(pred) != len(gold):
        return 0

    for i in range(len(gold)):
        found = False
        for j in range(len(pred)):
            if vectors_match(pred.iloc[j].tolist(), gold.iloc[i].tolist(), ignore_order_=ignore_order):
                found = True
                break
        if not found:
            return 0
    return 1

def run_random_eval(n=5):
    input_file = str(INPUT_DIR / "spider2-lite-snowflake.jsonl")
    all_instances = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            all_instances.append(json.loads(line))
    
    all_ids = [inst['instance_id'] for inst in all_instances]
    selected_ids = random.sample(all_ids, n)
    
    results = []
    
    gold_jsonl = str(GOLD_DIR / "spider2lite_eval.jsonl")
    eval_standards = {}
    with open(gold_jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            eval_standards[item['instance_id']] = item

    from backend.app.core.orchestrator import SemanticDINOrchestrator
    from backend.app.utils.logger import logger

    for instance_id in selected_ids:
        print(f"\n>>> RUNNING {instance_id}")
        inst_data = next(inst for inst in all_instances if inst['instance_id'] == instance_id)
        
        try:
            db_path = get_db_path(inst_data['db'])
            orchestrator = SemanticDINOrchestrator(db_directory=db_path, db_name=inst_data['db'])
            
            save_dir = os.path.join("results", inst_data['db'])
            os.makedirs(save_dir, exist_ok=True)
            md_path = os.path.join(save_dir, f"{instance_id}.md")
            logger.start_live_task_log(md_path)
            
            success_msg = orchestrator.execute_query(user_query=inst_data['question'], instance_id=instance_id)
            
            logger.stop_live_task_log()
            
            csv_path = Path(f"results/{inst_data['db']}/{instance_id}.csv")
            if not csv_path.exists() or os.path.getsize(csv_path) <= 1:
                results.append({"id": instance_id, "status": "EMPTY", "score": 0})
                continue
            
            pred_df = pd.read_csv(csv_path)
            gold_data = eval_standards.get(instance_id)
            if not gold_data:
                results.append({"id": instance_id, "status": "NO_GOLD", "score": 0})
                continue
            
            # This part needs the actual gold CSV to compare, which is usually in gold/results/
            gold_csv_path = GOLD_DIR / "results" / f"{instance_id}.csv"
            if not gold_csv_path.exists():
                results.append({"id": instance_id, "status": "GOLD_CSV_MISSING", "score": 0})
                continue
                
            gold_df = pd.read_csv(gold_csv_path)
            score = compare_pandas_table(pred_df, gold_df)
            results.append({"id": instance_id, "status": "DONE", "score": score})
            
        except Exception as e:
            print(f"Error on {instance_id}: {e}")
            results.append({"id": instance_id, "status": "ERROR", "score": 0})

    print("\n" + "="*30)
    print("  RANDOM EVAL SUMMARY")
    print("="*30)
    for r in results:
        print(f" {r['id']}: {r['status']} | Score: {r['score']}")
    
    total_score = sum(r['score'] for r in results)
    print(f"\nAverage Score: {total_score/n:.2f}")

if __name__ == "__main__":
    run_random_eval(3)
