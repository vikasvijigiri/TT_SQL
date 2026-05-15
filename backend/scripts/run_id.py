import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app.core.config import INPUT_DIR, get_db_path
from backend.app.core.orchestrator import SemanticDINOrchestrator
from backend.app.utils.logger import logger

def run_specific_eval(instance_id: str):
    input_file = str(INPUT_DIR / "spider2-lite-snowflake.jsonl")
    inst_data = None
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            if item['instance_id'] == instance_id:
                inst_data = item
                break
    
    if not inst_data:
        print(f"Error: Instance ID {instance_id} not found.")
        return

    print(f"\n>>> RUNNING {instance_id}")
    try:
        db_path = get_db_path(inst_data['db'])
        orchestrator = SemanticDINOrchestrator(db_directory=db_path, db_name=inst_data['db'])
        
        save_dir = os.path.join("results", inst_data['db'])
        os.makedirs(save_dir, exist_ok=True)
        
        result_sql = orchestrator.execute_query(user_query=inst_data['question'], instance_id=instance_id)
        print(f"\nFINAL SQL:\n{result_sql}")
        
    except Exception as e:
        print(f"Error on {instance_id}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_specific_eval(sys.argv[1])
    else:
        run_specific_eval("sf_bq050")
