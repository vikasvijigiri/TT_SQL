import os
import json
import time
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from app.services.pipeline_service import run_analysis_pipeline
from app.core.logger import Logger
from app.repositories.paths import InstancePaths, initialize_directories

from fastapi import Request

class BatchService:
    """
    Service for high-performance batch processing of Text-to-SQL tasks.
    """

    def __init__(self, model_name: str = None, config: Dict[str, Any] = None):
        from app.core.settings import settings
        self.config = config or {}
        self.model_name = model_name or self.config.get("llm_model") or settings.LLM_MODEL or "gpt-default"
        self.logger = logging.getLogger(__name__)
        self.antigravity_logger = Logger
        initialize_directories(self.model_name)

    def load_tasks(self, jsonl_path: str) -> List[Dict[str, Any]]:
        tasks = []
        if os.path.exists(jsonl_path):
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            tasks.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return tasks

    def process_single_task(self, 
                            task: Dict[str, Any], 
                            use_rag: bool = True, 
                            user_email: str = None,
                            project_slug: str = None,
                            config: Dict[str, Any] = None,
                            agents_list: Optional[List[str]] = None,
                            skip_existing: bool = False,
                            verbose: bool = False) -> Dict[str, Any]:
        """
        Processes a single task within the batch.
        """
        iid = task.get('instance_id', 'unknown')
        db_name = task.get('db')
        question = task.get('question')

        if skip_existing:
            from app.repositories.paths import get_model_results_dir
            model_dir = get_model_results_dir(self.model_name)
            csv_path = InstancePaths.csv(iid, model_dir)
            if csv_path.exists():
                return {"instance_id": iid, "status": "SKIPPED", "time": 0}

        try:
            start_t = time.time()
            
            # Run Pipeline
            final_state = run_analysis_pipeline(
                question=question,
                db_name=db_name,
                instance_id=iid,
                model_name=self.model_name,
                enabled_agents=agents_list,
                use_rag=use_rag,
                verbose=verbose,
                user_email=user_email,
                project_slug=project_slug,
                config_override=config or self.config
            )
            
            duration = time.time() - start_t
            
            is_fatal = final_state.error_message and "ERROR:" in final_state.error_message.upper()
            status = "FAILED" if is_fatal else "SUCCESS"
            
            return {
                "instance_id": iid,
                "status": status,
                "time": duration,
                "error": final_state.error_message if is_fatal else None,
                "sql": final_state.chosen_query
            }
            
        except Exception as e:
            self.logger.error(f"Error processing {iid}: {str(e)}")
            return {
                "instance_id": iid,
                "status": "ERROR",
                "time": 0,
                "error": str(e)
            }

    def run_batch(self, 
                  dataset_path: str = None, 
                  workers: int = 4, 
                  limit: int = 0, 
                  ids: Optional[List[str]] = None,
                  use_rag: bool = True,
                  user_email: str = None,
                  project_slug: str = None,
                  overwrite: bool = False,
                  agents: Optional[List[str]] = None,
                  verbose: bool = False) -> Dict[str, Any]:
        """
        Executes a batch of tasks in parallel.
        """
        path = dataset_path
        if not path:
            raise ValueError("dataset_path must be provided (legacy SPIDER_DATASET removed)")
        tasks = self.load_tasks(path)

        if ids:
            tasks = [t for t in tasks if str(t.get("instance_id")) in ids]

        if limit > 0:
            tasks = tasks[:limit]

        if verbose:
            self.antigravity_logger._verbose = True

        results = []
        self.logger.info(f"Starting batch run: {len(tasks)} tasks, {workers} workers")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_task = {
                executor.submit(
                    self.process_single_task,
                    task,
                    use_rag=use_rag,
                    user_email=user_email,
                    project_slug=project_slug,
                    agents_list=agents,
                    skip_existing=not overwrite,
                    verbose=verbose
                ): task
                for task in tasks
            }

            for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Batch Execution"):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    self.logger.error(f"Task generated exception: {e}")

        # Summary statistics
        summary = {
            "total": len(tasks),
            "passed": len([r for r in results if r["status"] == "SUCCESS"]),
            "failed": len([r for r in results if r["status"] in ["FAILED", "ERROR"]]),
            "skipped": len([r for r in results if r["status"] == "SKIPPED"]),
            "results": results
        }
        
        return summary

    async def run_batch_stream(self, 
                               dataset_path: str, 
                               user_email: str = None, 
                               user_name: str = None,
                               workers: int = 4,
                               use_rag: bool = True,
                               project_slug: str = None,
                               request: Request = None):
        """
        Streaming version of run_batch for SSE.
        """
        from app.repositories.paths import get_user_slug
        user_slug = get_user_slug(user_email=user_email, user_name=user_name)
        
        tasks = self.load_tasks(dataset_path)
        total = len(tasks)
        
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"
        
        # We run in a thread pool but yield as they complete
        with ThreadPoolExecutor(max_workers=workers) as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(
                    executor, 
                    self.process_single_task, 
                    task,
                    use_rag,
                    user_email,
                    project_slug,
                    self.config
                ) for task in tasks
            ]
            
            completed = 0
            for future in asyncio.as_completed(futures):
                if request and await request.is_disconnected():
                    # Terminate logic
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Batch processing aborted by user'})}\n\n"
                    break

                try:
                    res = await future
                    completed += 1
                    yield f"data: {json.dumps({'type': 'progress', 'completed': completed, 'total': total, 'current': res})}\n\n"
                except asyncio.CancelledError:
                    continue
        
        yield f"data: {json.dumps({'type': 'complete', 'status': 'finished'})}\n\n"

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="High-Performance Text-to-SQL Batch Runner")
    parser.add_argument("--dataset", type=str, help="Path to JSONL dataset")
    parser.add_argument("--model", type=str, help="Model name to use")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks")
    parser.add_argument("--ids", type=str, help="Comma-separated list of instance IDs")
    parser.add_argument("--no-rag", action="store_true", help="Disable RAG retrieval")
    parser.add_argument("--overwrite", action="store_true", help="Re-run existing results")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    id_list = [i.strip() for i in args.ids.split(",")] if args.ids else None
    
    service = BatchService(model_name=args.model)
    summary = service.run_batch(
        dataset_path=args.dataset,
        workers=args.workers,
        limit=args.limit,
        ids=id_list,
        use_rag=not args.no_rag,
        overwrite=args.overwrite,
        verbose=args.verbose
    )
    
    print("\nBatch Complete:")
    print(f"Total: {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Skipped: {summary['skipped']}")
