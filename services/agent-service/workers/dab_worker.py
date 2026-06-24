import sys
import os
import time
import uuid
import contextlib
import argparse
from pathlib import Path
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from api.db.database import SessionLocal
from api.db.models import TaskRun
from workers.dab.benchmark_loader import load_all_queries
from workers.dab.dab_orchestrator import run_dab_query
from core.utils.llm import LLMClient
from core.utils.logger import logger
from config.config import DAB_REPO
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_pending_tasks(db: Session, limit: int = 5) -> list[TaskRun]:
    # Fetch multiple pending tasks
    pending = db.query(TaskRun).filter(TaskRun.status == "PENDING", TaskRun.task_type == "dab_query").limit(limit).all()
    if not pending:
        return []
        
    claimed = []
    for task in pending:
        # Attempt to claim each using optimistic concurrency
        rows_affected = db.query(TaskRun).filter(
            TaskRun.id == task.id, 
            TaskRun.status == "PENDING"
        ).update({"status": "RUNNING"})
        
        if rows_affected == 1:
            claimed.append(task)
            
    db.commit()
    return claimed

def process_task(task_id: str, target_id: str, query_lookup: dict, worker_id: str):
    # Create an independent thread-local DB session and LLM client per thread
    db = SessionLocal()
    llm_client = LLMClient()
    try:
        task = db.query(TaskRun).filter(TaskRun.id == task_id).first()
        if not task:
            return
            
        print(f"\\n[Worker-{worker_id}] Thread claiming task: {task.id} -> {target_id}")
        
        parts = str(target_id).rsplit("_run", 1)
        query_key = parts[0]
        run_number = int(parts[1]) if len(parts) > 1 else 0
        
        q = query_lookup.get(query_key)
        if not q:
            print(f"[Worker-{worker_id}] ERROR: Could not find metadata for {query_key}")
            task.status = "FAILED"
            task.error_message = f"Query {query_key} not found"
            db.commit()
            return
            
        result = run_dab_query(q, llm_client=llm_client, run_number=run_number)
        
        if result["status"] == "passed":
            task.status = "COMPLETED"
        elif result["status"] == "error":
            task.status = "FAILED"
            task.error_message = result.get("error", "Unknown error")
        else:
            task.status = "COMPLETED"
            
        db.commit()
        print(f"[Worker-{worker_id}] Finished task: {task.id} -> {task.status}")
        
    except Exception as e:
        task = db.query(TaskRun).filter(TaskRun.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(e)
            db.commit()
        print(f"[Worker-{worker_id}] Exception on {task_id}: {e}")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Distributed DAB Worker")
    parser.add_argument("--dab_repo", type=str, default=str(DAB_REPO))
    args = parser.parse_args()

    worker_id = str(uuid.uuid4())[:8]
    print(f"\\n[Worker-{worker_id}] Starting ASYNC DAB distributed worker (10 threads)...")
    print(f"[Worker-{worker_id}] Connecting to SQLite TaskManager Queue...")
    
    all_queries = load_all_queries(args.dab_repo)
    query_lookup = { f"{q['dataset']}_{q['query_id']}": q for q in all_queries }
    
    db = SessionLocal()
    
    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                tasks = get_pending_tasks(db, limit=10)
                if not tasks:
                    print(f"\\r[Worker-{worker_id}] Waiting for jobs in queue...", end="", flush=True)
                    time.sleep(2.0)
                    continue
                    
                print(f"\\n[Worker-{worker_id}] Fetched {len(tasks)} tasks. Dispatching to threads...")
                
                futures = []
                for task in tasks:
                    # Pass IDs instead of SQLAlchemy objects to threads to prevent session sharing issues
                    futures.append(executor.submit(process_task, task.id, task.target_id, query_lookup, worker_id))
                    
                for future in as_completed(futures):
                    future.result() # Wait for batch to finish
                    
    except KeyboardInterrupt:
        print(f"\n[Worker-{worker_id}] Shutting down gracefully.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
