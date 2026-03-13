import os
import sys
import argparse
import pandas as pd
from pathlib import Path
import tempfile
import shutil

# Project root - go up from app/tools/ to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(PROJECT_ROOT, "gold"))

try:
    from evaluate import evaluate_spider2sql
except ImportError:
    print("Error: Could not import evaluate from gold/evaluate.py. Make sure 'gold' directory exists.")
    sys.exit(1)

from app.services.evaluation_service import EvaluationService
from app.services.evaluation.failure_service import FailureService

def main():
    parser = argparse.ArgumentParser(description="Collect failed examples from Spider2 evaluation")
    parser.add_argument("--model", type=str, help="Model name (e.g. bedrock/openai.gpt-4o)")
    parser.add_argument("--result_dir", type=str, help="Direct path to results directory (overrides --model)")
    parser.add_argument("--gold_dir", type=str, default="gold", help="Path to gold directory")
    parser.add_argument("--output", type=str, default="failed_ids.csv", help="Output CSV file name")
    
    args = parser.parse_args()
    
    # Determine result_dir
    if args.result_dir:
        result_dir_val = args.result_dir
    elif args.model:
        # Match the naming convention in paths.py
        safe_name = args.model.replace("/", "_").replace(":", "_")
        result_dir_val = os.path.join(PROJECT_ROOT, "results", safe_name, "csv")
    else:
        print("Error: Must provide --model or --result_dir")
        sys.exit(1)
        
    if not os.path.exists(result_dir_val):
        print(f"Error: Result directory not found: {result_dir_val}")
        print(f"Did you run the batch pipeline for this model yet?")
        sys.exit(1)

    print(f"Evaluating results in: {result_dir_val}")
    print(f"Using gold directory: {args.gold_dir}")
    
    # Mock args object for evaluate_single_sql_instance
    eval_service = EvaluationService()
    failure_service = FailureService(eval_service)
    
    # Run evaluation and collect failures
    # This is a bit of a simplification, in a real scenario we'd call the generalized eval
    # but for the CLI script we can mock the args and run it.
    
    class EvalArgs:
        mode = "exec_result"
        result_dir = result_dir_val
        gold_dir = args.gold_dir
        gold_exec_dir = None
        eval_jsonl = None
        meta_jsonl = None
        db_dir = None
        max_workers = 20
        temp_dir = None
        
    temp_path = Path(tempfile.mkdtemp(prefix="collect_fail_"))
    try:
        results = eval_service.run_generalized_evaluation(EvalArgs(), temp_path)
        failure_service.collect_failures(results, args.output)
    finally:
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)

if __name__ == "__main__":
    main()
