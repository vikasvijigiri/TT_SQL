import json
import os
import argparse
from multiprocessing import Pool, cpu_count
from functools import partial
from pathlib import Path

from app.services.rag_service import query_qdrant
from app.models.config import settings
from app.services.logger import Logger
from app.models.paths import INPUT_QUERIES_DIR, DATA_DIR, PROJECT_ROOT

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def _process_single_question(data, results_dir=None, metadata_dir=None):
    """Worker function for multiprocessing."""
    try:
        instance_id = data.get("instance_id")
        question = data.get("question")
        collection = data.get("db")
        
        if not question:
            return None
        
        # In child processes, we should still use the Logger for clear tracing
        Logger.log(f"Process [{os.getpid()}] handling Instance: {instance_id}")
        
        res = query_qdrant(
            query_text=question,
            top_k=settings.EMBEDDING_SIZE,
            collection_name=collection or settings.COLLECTION_NAME,
            instance_id=instance_id,
            results_dir=results_dir,
            metadata_dir=metadata_dir
        )
        return res
    except Exception as e:
        Logger.log(f"Worker Error for Index {data.get('instance_id')}: {str(e)}", level="ERROR")
        return None

def process_questions(jsonl_path, results_dir=None, metadata_dir=None, num_processes=None):
    """
    Parses instance_id, questions, and schema (db) from a JSONL file
    and runs the RAG pipeline for each using multiprocessing.
    """
    if not os.path.exists(jsonl_path):
        Logger.log(f"Batch Input Not Found: {jsonl_path}", level="ERROR")
        return

    questions_data = []
    Logger.log(f"Loading questions from {jsonl_path}...")
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                questions_data.append(json.loads(line))
            except json.JSONDecodeError as e:
                Logger.log(f"JSON Parse Error in batch: {str(e)}", level="WARNING")

    if not questions_data:
        Logger.log("No questions found in file.", level="WARNING")
        return

    # Determine optimal number of processes
    if num_processes is None:
        num_processes = min(len(questions_data), cpu_count())
    
    Logger.log(f"Starting parallel batch process with {num_processes} workers...")
    
    # Use partial to pass directory overrides to worker
    worker_func = partial(_process_single_question, results_dir=results_dir, metadata_dir=metadata_dir)
    
    results = []
    with Pool(processes=num_processes) as pool:
        results = [r for r in pool.map(worker_func, questions_data) if r is not None]

    # Save consolidated results
    if results:
        output_path = DATA_DIR / 'batch_results_all.json'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        Logger.log(f"Batch Complete: {len(results)} queries processed. Summary saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parallel batch process questions.")
    parser.add_argument("--input-jsonl", type=str, default=settings.BATCH_INPUT_PATH, help=f"Path to JSONL file (default: {settings.BATCH_INPUT_PATH})")
    parser.add_argument("--results-dir", type=str, help="Override results directory")
    parser.add_argument("--metadata-dir", type=str, help="Override metadata directory")
    parser.add_argument("--workers", type=int, default=settings.PARALLEL_WORKERS, help=f"Number of worker processes (default: {settings.PARALLEL_WORKERS})")
    args = parser.parse_args()

    # Resolve path: If relative, try to resolve from PROJECT_ROOT or as is
    input_file = Path(args.input_jsonl)
    if not input_file.is_absolute():
        # Try relative to PROJECT_ROOT first
        potential_path = PROJECT_ROOT / args.input_jsonl
        if potential_path.exists():
            input_file = potential_path
        else:
            # Fallback to INPUT_QUERIES_DIR if it's just a filename
            input_file = INPUT_QUERIES_DIR / args.input_jsonl
    
    process_questions(str(input_file), results_dir=args.results_dir, metadata_dir=args.metadata_dir, num_processes=args.workers)
