import os
import sys
import argparse
import pandas as pd
from pathlib import Path
import tempfile
import shutil

# Add gold directory to path to allow importing evaluate
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "gold"))

try:
    from evaluate import evaluate_spider2sql
except ImportError:
    print("Error: Could not import evaluate from gold/evaluate.py. Make sure 'gold' directory exists.")
    sys.exit(1)

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
    
    # Mock args object for evaluate_spider2sql
    class EvalArgs:
        mode = "exec_result"
        result_dir = result_dir_val
        gold_dir = args.gold_dir
        is_sql_debug = False
        max_workers = 20
        timeout = 60
        temp_dir = None
        
    # Create temp dir for evaluation
    temp_path = Path(tempfile.mkdtemp(prefix="collect_fail_"))
    
    try:
        # Run evaluation
        # evaluate_spider2sql returns a list of dicts: {'instance_id': str, 'score': int, ...}
        results = evaluate_spider2sql(EvalArgs(), temp_path)
        
        # Filter failures (score != 1 means failure)
        failed_ids = []
        for r in results:
            if r["score"] != 1:
                failed_ids.append(r["instance_id"])
        
        # Save to CSV
        output_path = args.output
        if failed_ids:
            pd.DataFrame({"instance_id": failed_ids}).to_csv(output_path, index=False)
            print(f"\nFound {len(failed_ids)} failed examples.")
            print(f"Failed IDs saved to: {os.path.abspath(output_path)}")
        else:
            print("\nNo failures found! All examples passed.")
            # Create empty CSV just in case
            pd.DataFrame({"instance_id": []}).to_csv(output_path, index=False)
            
    except Exception as e:
        print(f"An error occurred during evaluation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)

if __name__ == "__main__":
    main()
