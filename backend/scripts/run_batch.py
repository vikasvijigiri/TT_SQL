import os
import json
import time
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from dotenv import load_dotenv
import sys

# Import the new pure-Python pipeline runner
from app.services.engines.pipeline_service import run_analysis_pipeline
from app.services.utils.logger import Logger
from app.repositories.registry.paths import InstancePaths, SPIDER_DATASET

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

def process_task(task, model_name, use_rag, agents_list=None, skip_existing=False, rag_source="none", rag_limit=5, verbose=False):
    iid = task.get('instance_id', 'unknown')
    db_name = task.get('db')
    question = task.get('question')
    
    # Check if result already exists (optional)
    if skip_existing:
        csv_path = InstancePaths.csv(iid, model_name)
        if csv_path.exists():
            return {"instance_id": iid, "status": "SKIPPED", "time": 0}

    try:
        start_t = time.time()
        
        # Run Pipeline
        final_state = run_analysis_pipeline(
            question=question,
            db_name=db_name,
            instance_id=iid,
            model_name=model_name,
            enabled_agents=agents_list,
            use_rag=use_rag,
            verbose=verbose
        )
        
        duration = time.time() - start_t
        
        # Determine status and error message based on the final_state
        is_fatal = final_state.error_message and "ERROR:" in final_state.error_message.upper()
        status = "FAILED" if is_fatal else "SUCCESS"
        
        error_msg = "Unknown Error"
        if final_state and final_state.error_message:
            error_msg = final_state.error_message
        elif is_fatal and captured_text:
            error_msg = captured_text.strip().split('\n')[-1] # Put last line of error log
            
        return {
            "instance_id": iid,
            "status": status,
            "time": duration,
            "error": error_msg,
            "full_error": captured_text
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Error processing {iid}:\n{traceback.format_exc()}")
        return {
            "instance_id": iid,
            "status": "ERROR",
            "time": 0,
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description="High-Performance Text-to-SQL Batch Runner")
    # SPIDER_DATASET already imported at top level
    parser.add_argument("--dataset", type=str, default=str(SPIDER_DATASET), help="Path to JSONL dataset")
    parser.add_argument("--model", type=str, default=os.getenv("LLM_MODEL"), help="Model name to use")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 for all)")
    parser.add_argument("--rag", type=str, default="qdrant", help="RAG source (none, qdrant)")
    parser.add_argument("--use-rag", action="store_true", default=True, help="Use Qdrant vector store for column retrieval")
    parser.add_argument("--top-2", action="store_true", help="Limit to top 2 tables only (RAG)")
    parser.add_argument("--overwrite", action="store_true", default=False, help="Re-run even if CSV results already exist")
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated list of instance IDs to process")
    parser.add_argument("--agents", type=str, default=None, help="Comma-separated list of agents to run")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose terminal logging")
    
    args = parser.parse_args()
    initialize_directories(args.model)
    
    # Enable verbose terminal logging if requested
    if args.verbose:
        from app.services.utils.logger import Logger
        Logger._verbose = True
    
    # Initialize AWS/OpenAI envs if needed (handled by load_dotenv)
    
    logger.info(f"ðŸš€ Starting Batch Run with {args.workers} workers")
    logger.info(f"ðŸ“‚ Dataset: {args.dataset}")
    logger.info(f"ðŸ¤– Model: {args.model}")
    
    tasks = load_tasks(args.dataset)
    
    # Filter by IDs if provided
    if args.ids:
        target_ids = [i.strip() for i in args.ids.split(",")]
        tasks = [t for t in tasks if t.get("instance_id") in target_ids]
        logger.info(f"ðŸŽ¯ Filtered for {len(target_ids)} specific IDs.")

    if args.limit > 0:
        tasks = tasks[:args.limit]
        
    logger.info(f"ðŸ”¥ Processing {len(tasks)} tasks...")
    
    config = {
        "model_name": args.model,
        "rag_source": args.rag,
        "use_rag": args.use_rag,
        "rag_limit": 2 if args.top_2 else 2, # Defaults to 2 now anyway as requested
        "verbose": args.verbose,
        "skip_existing": not args.overwrite
    }
    # Parse agents string into a list
    agents_list = [agent.strip() for agent in args.agents.split(',')] if args.agents else []

    # The config dictionary is no longer directly passed to process_task,
    # but its components are passed as individual arguments.
    # We still need to determine rag_limit and skip_existing here.
    rag_limit_val = 2 if args.top_2 else 5 # Defaults to 5 now, not 2
    skip_existing_val = not args.overwrite
    
    results = []
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                process_task, 
                task, 
                args.model, 
                args.use_rag,
                agents_list, # Pass the parsed agents list
                skip_existing_val,
                args.rag,
                rag_limit_val,
                args.verbose
            ): task 
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
                    tqdm.write(f"[PASS] {result['instance_id']} ({result['time']:.1f}s)")
                elif result["status"] == "SKIPPED":
                    pass # Silent skip
                else:
                    tqdm.write(f"[FAIL] {result['instance_id']} ({result['error']})")
                    
            except Exception as exc:
                tqdm.write(f"[ERROR] Task {task.get('instance_id')} generated an exception: {exc}")

    # Summary
    passed = len([r for r in results if r["status"] == "SUCCESS"])
    failed = len([r for r in results if r["status"] in ["FAILED", "ERROR"]])
    skipped = len([r for r in results if r["status"] == "SKIPPED"])
    
    logger.info("="*40)
    logger.info("Batch Complete")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Skipped: {skipped}")
    logger.info("="*40)

if __name__ == "__main__":
    main()

