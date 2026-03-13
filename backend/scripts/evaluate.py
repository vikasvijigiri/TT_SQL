import argparse
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Ensure PYTHONPATH includes project root
sys.path.append(os.getcwd())

from app.services.evaluation_service import EvaluationService

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="CLI Wrapper for TT-SQL Evaluation")
    parser.add_argument("--mode", type=str, choices=["sql", "exec_result"], default="sql")
    parser.add_argument("--result_dir", type=str, required=True, help="Path to predicted SQL or CSV folder")
    parser.add_argument("--gold_dir", type=str, default="evaluation", help="Directory containing gold SQL and exec files")
    parser.add_argument("--gold_exec_dir", type=str, help="Subfolder in gold_dir containing ground truth CSVs")
    parser.add_argument("--eval_jsonl", type=str, help="Path to evaluation standards JSONL")
    parser.add_argument("--meta_jsonl", type=str, help="Path to metadata JSONL (for mapping instances to DBs)")
    parser.add_argument("--db_dir", type=str, help="Directory containing .sqlite databases")
    parser.add_argument("--max_workers", type=int, default=16)
    parser.add_argument("--temp_dir", type=str, default=None)
    
    args = parser.parse_args()
    service = EvaluationService()

    # Setup temp path
    auto_temp = False
    if args.temp_dir:
        temp_path = Path(args.temp_dir).expanduser().resolve()
        os.makedirs(temp_path, exist_ok=True)
    else:
        temp_path = Path(tempfile.mkdtemp(prefix="tt_eval_"))
        auto_temp = True

    try:
        service.run_generalized_evaluation(args, temp_path)
    finally:
        if auto_temp:
            shutil.rmtree(temp_path, ignore_errors=True)

if __name__ == "__main__":
    main()
