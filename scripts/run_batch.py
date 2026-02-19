import os
import json
import time
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from dotenv import load_dotenv
import sys

# Ensure src is in python path (scripts/ -> project root -> src/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

# Import the new pure-Python pipeline runner
from tt_sql.core.pipeline_runner import run_analysis_pipeline
from tt_sql.core.logger import Logger
from tt_sql.core.paths import InstancePaths

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def load_tasks(jsonl_path):
    tasks = []
    if os.path.exists(jsonl_path):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    tasks.append(json.loads(line))
    return tasks

def process_task(task, config):
    iid = task.get('instance_id', 'unknown')
    db_name = task.get('db')
    question = task.get('question')
    
    # Check if result already exists (optional)
    if config.get("skip_existing"):
        csv_path = InstancePaths.csv(iid, config["model_name"])
        if csv_path.exists():
            return {"instance_id": iid, "status": "SKIPPED", "time": 0}

    try:
        start_t = time.time()
        
        # Run Pipeline
        final_state, _, is_fatal, _ = run_analysis_pipeline(
            question=question,
            db_name=db_name,
            instance_id=iid,
            model_name=config["model_name"],
            rag_source=config.get("rag_source", "none"),
            output_handler=None, # Use silent handler usually
            stop_checker=None
        )
        
        duration = time.time() - start_t
        status = "FAILED" if is_fatal else "SUCCESS"
        
        return {
            "instance_id": iid,
            "status": status,
            "time": duration,
            "error": final_state.error_message if final_state else "Unknown Error"
        }
        
    except Exception as e:
        logger.error(f"Error processing {iid}: {e}")
        return {
            "instance_id": iid,
            "status": "ERROR",
            "time": 0,
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description="High-Performance Text-to-SQL Batch Runner")
    parser.add_argument("--dataset", type=str, default=os.path.join(PROJECT_ROOT, "data", "spider2-lite1.jsonl"), help="Path to JSONL dataset")
    parser.add_argument("--model", type=str, default=os.getenv("LLM_MODEL", "gpt-4o"), help="Model name")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 for all)")
    parser.add_argument("--rag", type=str, default="none", help="RAG source (none, qdrant)")
    parser.add_argument("--overwrite", action="store_true", default=False, help="Re-run even if CSV results already exist")
    
    args = parser.parse_args()
    
    # Initialize AWS/OpenAI envs if needed (handled by load_dotenv)
    
    logger.info(f"🚀 Starting Batch Run with {args.workers} workers")
    logger.info(f"📂 Dataset: {args.dataset}")
    logger.info(f"🤖 Model: {args.model}")
    
    tasks = load_tasks(args.dataset)
    if args.limit > 0:
        tasks = tasks[:args.limit]
        
    logger.info(f"🔥 Processing {len(tasks)} tasks...")
    
    config = {
        "model_name": args.model,
        "rag_source": args.rag,
        "skip_existing": not args.overwrite
    }
    
    results = []
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(process_task, task, config): task 
            for task in tasks
        }
        
        # Use tqdm for progress bar
        for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Processing"):
            task = future_to_task[future]
            try:
                result = future.result()
                results.append(result)
                
                # Real-time status logging
                if result["status"] == "SUCCESS":
                    tqdm.write(f"✅ {result['instance_id']} ({result['time']:.1f}s)")
                elif result["status"] == "SKIPPED":
                    pass # Silent skip
                else:
                    tqdm.write(f"❌ {result['instance_id']} ({result['error']})")
                    
            except Exception as exc:
                tqdm.write(f"💥 Task {task.get('instance_id')} generated an exception: {exc}")

    # Summary
    passed = len([r for r in results if r["status"] == "SUCCESS"])
    failed = len([r for r in results if r["status"] in ["FAILED", "ERROR"]])
    skipped = len([r for r in results if r["status"] == "SKIPPED"])
    
    logger.info("="*40)
    logger.info(f"🎉 Batch Complete")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"⏭️ Skipped: {skipped}")
    logger.info("="*40)

if __name__ == "__main__":
    main()
