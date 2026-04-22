import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable
from tqdm import tqdm
from .pipeline_runner import run_analysis_pipeline
from .logger import Logger
from .paths import InstancePaths

class BatchRunner:
    """
    Core engine for running Text2SQL pipeline in batch.
    Handles parallel execution, progress tracking, and unified reporting.
    """
    
    def __init__(self, 
                 model_name: str, 
                 workers: int = 4, 
                 use_rag: bool = False, 
                 rag_source: str = "none",
                 overwrite: bool = False,
                 verbose: bool = False):
        self.model_name = model_name
        self.workers = workers
        self.use_rag = use_rag
        self.rag_source = rag_source
        self.overwrite = overwrite
        self.verbose = verbose
        
        if verbose:
            Logger._verbose = True

    def process_single_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        iid = task.get('instance_id', 'unknown')
        db_name = task.get('db')
        question = task.get('question')
        ext_knowledge = task.get('external_knowledge')
        
        # Unified folder check - skip if already exists
        if not self.overwrite:
            csv_path = InstancePaths.csv(iid, self.model_name)
            if csv_path.exists():
                return {"instance_id": iid, "status": "SKIPPED", "time": 0}

        try:
            start_t = time.time()
            
            # Execute the core analysis pipeline
            final_state, captured_transcript, is_fatal, _ = run_analysis_pipeline(
                question=question,
                db_name=db_name,
                instance_id=iid,
                model_name=self.model_name,
                rag_source=self.rag_source,
                use_rag=self.use_rag,
                verbose=self.verbose,
                external_knowledge=ext_knowledge
            )
            
            duration = time.time() - start_t
            status = "FAILED" if is_fatal else "SUCCESS"
            
            error_msg = ""
            if is_fatal and final_state:
                error_msg = final_state.error_message or "Pipeline Fatal Error"
            
            return {
                "instance_id": iid,
                "status": status,
                "time": duration,
                "error": error_msg
            }
            
        except Exception as e:
            return {
                "instance_id": iid,
                "status": "ERROR",
                "time": 0,
                "error": str(e)
            }

    def run(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Executes a list of tasks in parallel."""
        results = []
        
        Logger.log(f"🚀 Starting Batch Runner | Model: {self.model_name} | Workers: {self.workers}")
        
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_task = {
                executor.submit(self.process_single_task, task): task 
                for task in tasks
            }
            
            for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Processing Batch"):
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result["status"] == "SUCCESS":
                        tqdm.write(f"[PASS] {result['instance_id']} ({result['time']:.1f}s)")
                    elif result["status"] == "FAILED":
                        tqdm.write(f"[FAIL] {result['instance_id']} -> {result['error']}")
                    elif result["status"] == "ERROR":
                        tqdm.write(f"[ERR!] {result['instance_id']} -> {result['error']}")
                        
                except Exception as exc:
                    tqdm.write(f"[CRITICAL] Unexpected Exception: {exc}")

        # Summary
        passed = len([r for r in results if r["status"] == "SUCCESS"])
        failed = len([r for r in results if r["status"] in ["FAILED", "ERROR"]])
        skipped = len([r for r in results if r["status"] == "SKIPPED"])
        
        Logger.log_divider()
        Logger.log(f"BATCH COMPLETE: {passed} Passed, {failed} Failed, {skipped} Skipped.")
        Logger.log_divider()
        
        return results
