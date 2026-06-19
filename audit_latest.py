import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

ROOT_DIR = Path("c:/Users/VikasVijigiri/Documents/TT_SQL_V2/backend/agent")
sys.path.insert(0, str(ROOT_DIR))

from agent.app.db.database import SessionLocal
from agent.app.db.models import Evaluation, TaskRun

def main():
    db = SessionLocal()
    try:
        # Check TaskRun queue to see how many of the 270 are finished
        all_tasks = db.query(TaskRun).filter(TaskRun.task_type == "dab_query").all()
        total_tasks = len(all_tasks)
        pending_tasks = sum(1 for t in all_tasks if t.status == "PENDING")
        running_tasks = sum(1 for t in all_tasks if t.status == "RUNNING")
        completed_tasks = sum(1 for t in all_tasks if t.status == "COMPLETED")
        failed_tasks = sum(1 for t in all_tasks if t.status == "FAILED")
        
        print("=== TASK QUEUE STATUS ===")
        print(f"Total Enqueued: {total_tasks}")
        print(f"Pending: {pending_tasks}")
        print(f"Running: {running_tasks}")
        print(f"Completed: {completed_tasks}")
        print(f"Failed (Execution Error): {failed_tasks}")
        if total_tasks > 0:
            print(f"Finished overall: {completed_tasks + failed_tasks}/{total_tasks}\n")
        else:
            print("No tasks in queue. \n")

        cutoff_time = datetime.now() - timedelta(hours=24)
        
        recent_evals = db.query(Evaluation).order_by(Evaluation.timestamp.desc()).limit(1000).all()
        batch_evals = [e for e in recent_evals if e.timestamp >= cutoff_time]
        
        if not batch_evals:
            print("No evaluations found in the last 24 hours.")
            return
            
        print(f"=== BATCH EVALUATION AUDIT (Last 24 Hours) ===")
        print(f"Time range evaluated: {batch_evals[-1].timestamp} to {batch_evals[0].timestamp}")
        print(f"Total Evaluation Records: {len(batch_evals)}")
        
        queries_dict = {}
        for ev in batch_evals:
            if ev.instance_id not in queries_dict:
                queries_dict[ev.instance_id] = []
            queries_dict[ev.instance_id].append(ev)
            
        total_unique_queries = len(queries_dict)
        passed_runs = sum(1 for e in batch_evals if e.passed)
        failed_runs = len(batch_evals) - passed_runs
        
        print(f"\nUnique Queries Evaluated: {total_unique_queries}/54")
        print(f"Total Individual Slots Evaluated: {len(batch_evals)}")
        print(f"Total Individual Passes: {passed_runs}")
        print(f"Total Individual Failures: {failed_runs}")
        
        pass_at_1 = (passed_runs / len(batch_evals)) * 100 if len(batch_evals) > 0 else 0
        print(f"Overall Pass@1 Accuracy: {pass_at_1:.1f}%\n")
        
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
