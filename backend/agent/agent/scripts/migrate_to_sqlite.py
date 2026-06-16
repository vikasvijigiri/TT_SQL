import os
import json
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, 'backend')
from app.db.database import SessionLocal, engine, Base
from app.db.models import Evaluation
from app.core.config import DAB_RESULTS_DIR

def migrate():
    db = SessionLocal()
    count = 0
    if not DAB_RESULTS_DIR.exists():
        print(f"Directory not found: {DAB_RESULTS_DIR}")
        return
        
    for root, _, files in os.walk(DAB_RESULTS_DIR):
        for file in files:
            if file.endswith("_eval.json"):
                filepath = Path(root) / file
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Extract run_suffix from filename (e.g. query1_run2_eval.json -> _run2)
                    filename = filepath.stem # query1_run2_eval
                    base_part = f"query{data.get('query_id')}"
                    rest = filename[len(base_part):]
                    run_suffix = rest.replace("_eval", "")
                    
                    ts_str = data.get("timestamp")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str)
                        except:
                            ts = datetime.utcnow()
                    else:
                        ts = datetime.utcnow()
                        
                    eval_record = Evaluation(
                        dataset=data.get("dataset"),
                        query_id=data.get("query_id"),
                        instance_id=data.get("instance_id"),
                        run_suffix=run_suffix,
                        passed=data.get("passed", False),
                        reason=data.get("reason", ""),
                        method=data.get("method", ""),
                        ground_truth=data.get("ground_truth", ""),
                        agent_answer_snippet=data.get("agent_answer_snippet", ""),
                        elapsed_s=data.get("elapsed_s"),
                        input_tokens=data.get("input_tokens"),
                        output_tokens=data.get("output_tokens"),
                        timestamp=ts
                    )
                    db.add(eval_record)
                    count += 1
                except Exception as e:
                    print(f"Failed to migrate {filepath}: {e}")
                    
    db.commit()
    db.close()
    print(f"Successfully migrated {count} evaluation records to SQLite.")

if __name__ == "__main__":
    migrate()
