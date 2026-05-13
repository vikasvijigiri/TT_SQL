import json
import os
import time
import argparse
import csv
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import sys
from pathlib import Path

# Add project root to path to allow absolute imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.pipeline import Text2SQLPipeline
from src.utils.logger import logger

class BatchRunner:
    def __init__(self, metadata_dir: str, workers: int = 4, output_dir: str = "results", filter_id: Optional[str] = None, filter_db: Optional[str] = None):
        self.metadata_dir = metadata_dir
        self.workers = workers
        self.output_dir = Path(output_dir)
        self.filter_id = filter_id
        self.filter_db = filter_db
        self.pipelines: Dict[str, Text2SQLPipeline] = {}
        
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_pipeline(self, db_name: str) -> Text2SQLPipeline:
        if db_name not in self.pipelines:
            # Check for metadata file in metadata_dir
            metadata_path = os.path.join(self.metadata_dir, f"{db_name}.json")
            if not os.path.exists(metadata_path):
                logger.error(f"Metadata not found for DB: {db_name} at {metadata_path}")
                raise FileNotFoundError(f"Metadata file {metadata_path} not found")
            
            logger.info(f"Initializing pipeline for DB: {db_name}")
            self.pipelines[db_name] = Text2SQLPipeline(metadata_path)
        return self.pipelines[db_name]

    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        iid = task.get("instance_id")
        db_name = task.get("db")
        question = task.get("question")
        
        if not iid or not db_name or not question:
            return {"instance_id": iid, "status": "ERROR", "error": "Missing required fields"}

        # Initialize DB-specific directory
        db_results_dir = self.output_dir / db_name
        db_results_dir.mkdir(parents=True, exist_ok=True)

        # Load external knowledge if specified
        external_knowledge = ""
        ek_path = task.get("external_knowledge")
        if ek_path:
            # Try absolute, then relative to resources/documents
            full_ek_path = ek_path if os.path.isabs(ek_path) else os.path.join("resources/documents", ek_path)
            if os.path.exists(full_ek_path):
                with open(full_ek_path, 'r', encoding='utf-8') as f:
                    external_knowledge = f.read()
                    logger.info(f"Loaded external knowledge from {ek_path}")
            else:
                logger.warning(f"External knowledge file not found: {ek_path}")

        # 0. Initialize Markdown Log with Header
        md_file = db_results_dir / f"{iid}.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(f"# Reasoning Log for {iid}\n\n")
            f.write(f"**Question:** {question}\n\n")
            f.write("## 1. Execution Log (Live Mirror)\n")
            f.write("```text\n") # Start code block for live logs

        try:
            logger.start_live_task_log(str(md_file)) # Start appending to the md file
            
            pipeline = self.get_pipeline(db_name)
            start_t = time.time()
            result = pipeline.run(question, external_knowledge=external_knowledge)
            duration = time.time() - start_t
            
            logger.stop_live_task_log()
            
            # Close the code block and add final results
            with open(md_file, 'a', encoding='utf-8') as f:
                f.write("```\n\n") # Close live log block
                
                if result.intent:
                    f.write("## 2. Intent Analysis (Final)\n")
                    f.write(f"```json\n{json.dumps(result.intent.model_dump(), indent=2)}\n```\n\n")
                
                if result.sql:
                    f.write("## 3. Generated SQL\n")
                    f.write(f"```sql\n{result.sql}\n```\n\n")
                
                if result.error:
                    f.write(f"## ⚠️ Error\n```text\n{result.error}\n```\n\n")
                
                if result.rows:
                    from tabulate import tabulate
                    f.write("## 4. Execution Preview (Top 5 Rows)\n")
                    f.write("```text\n")
                    preview = result.rows[:5]
                    f.write(tabulate(preview, headers="keys", tablefmt="pretty"))
                    f.write("\n```\n\n")

                f.write(f"**Final Confidence:** {result.confidence:.2f}\n")
                f.write(f"**Latency:** {result.latency_ms:.0f}ms\n")

            # Save SQL and CSV separately (Only if generated)
            if result.sql:
                sql_file = db_results_dir / f"{iid}.sql"
                with open(sql_file, 'w', encoding='utf-8') as f:
                    f.write(result.sql)

            if result.rows:
                csv_file = db_results_dir / f"{iid}.csv"
                keys = result.rows[0].keys()
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    dict_writer = csv.DictWriter(f, fieldnames=keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(result.rows)

            return {
                "instance_id": iid,
                "db": db_name,
                "status": "SUCCESS" if not result.error else "FAILED",
                "time": duration,
                "sql": result.sql,
                "error": result.error,
                "confidence": result.confidence
            }
        except Exception as e:
            logger.stop_live_task_log()
            with open(md_file, 'a', encoding='utf-8') as f:
                f.write(f"\n\n## ⚠️ Critical Failure\n```text\n{str(e)}\n```\n")
            logger.error(f"Error processing {iid}: {str(e)}")
            return {"instance_id": iid, "db": db_name, "status": "ERROR", "error": str(e)}

    def run(self, input_file: str):
        tasks = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    task = json.loads(line)
                    # Apply filters
                    if self.filter_id and task.get("instance_id") != self.filter_id:
                        continue
                    if self.filter_db and task.get("db") != self.filter_db:
                        continue
                    tasks.append(task)
        
        if not tasks:
            logger.warning("No tasks found matching the criteria.")
            return

        logger.info(f"Starting Batch Runner | Tasks: {len(tasks)} | Workers: {self.workers}")
        
        results = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_task = {executor.submit(self.process_task, t): t for t in tasks}
            
            for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Processing Tasks"):
                res = future.result()
                results.append(res)
                
                # Console feedback
                if res["status"] == "SUCCESS":
                    tqdm.write(f"[PASS] {res['instance_id']} ({res['time']:.1f}s)")
                else:
                    tqdm.write(f"[FAIL] {res['instance_id']} -> {res.get('error', 'Unknown Error')}")
                
        # Final Summary
        success = len([r for r in results if r["status"] == "SUCCESS"])
        failed = len([r for r in results if r["status"] == "FAILED"])
        errors = len([r for r in results if r["status"] == "ERROR"])
        
        logger.info("-" * 50)
        logger.info(f"BATCH COMPLETE: {success} Success, {failed} Failed, {errors} Errors")
        logger.info("-" * 50)
        
        # Save summary
        summary_file = self.output_dir / "batch_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Deterministic Text2SQL Batch Runner")
    parser.add_argument("--input", type=str, required=True, help="Path to input .jsonl file")
    parser.add_argument("--metadata_dir", type=str, default="resources/metadata", help="Directory containing metadata JSON files")
    parser.add_argument("--output", type=str, default="results", help="Base directory for results")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--id", type=str, help="Filter by instance_id")
    parser.add_argument("--db", type=str, help="Filter by database name")
    
    args = parser.parse_args()
    
    runner = BatchRunner(
        metadata_dir=args.metadata_dir, 
        workers=args.workers, 
        output_dir=args.output,
        filter_id=args.id,
        filter_db=args.db
    )
    runner.run(args.input)

if __name__ == "__main__":
    main()
