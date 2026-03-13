import os
import json
import argparse
import sys
import subprocess
from pathlib import Path

# Ensure PYTHONPATH includes project root
sys.path.append(os.getcwd())

from app.models.paths import PROJECT_ROOT, get_next_instance_id, INPUT_QUERIES_DIR
from app.models.config import settings

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_command(cmd_list):
    """Run a subprocess command and stream output."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    try:
        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            cwd=str(PROJECT_ROOT),
            env=env
        )
        for line in process.stdout:
            print(line, end='', flush=True)
        process.wait()
        return process.returncode == 0
    except Exception as e:
        print(f"[Error] Command execution failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Phase 2: RAG-based Analysis Execution")
    parser.add_argument("--question", help="The natural language question to analyze")
    parser.add_argument("--instance-id", help="Target instance ID from input JSONL (e.g. q001)")
    parser.add_argument("--input", help="Path to input JSONL for context lookup (default: sample.jsonl)")
    parser.add_argument("--db", help="Override database/schema name")
    parser.add_argument("--model", default=settings.LLM_MODEL, help="Model name to use")
    
    args = parser.parse_args()
    
    # 1. Context Resolution
    question = args.question
    db_name = args.db
    instance_id = args.instance_id
    
    if instance_id:
        detected_q = None
        detected_db = None
        # Try standard locations if not specified
        jsonl_candidates = []
        if args.input:
            jsonl_candidates.append(Path(args.input))
        else:
            for cand in ["spider2-lite.jsonl", "sample.jsonl", "user_questions.jsonl"]:
                jsonl_candidates.append(INPUT_QUERIES_DIR / cand)

        for jsonl_path in jsonl_candidates:
            if not jsonl_path.exists():
                continue
            
            print(f"🔍 Checking for instance '{instance_id}' in {jsonl_path}...")
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    if not line: continue
                    try:
                        data = json.loads(line)
                        current_id = str(data.get("instance_id", "")).strip()
                        target_id = str(instance_id).strip()
                        if current_id == target_id:
                            print(f"  [Match Found] Instance: {instance_id}")
                            detected_q = data.get("question")
                            detected_db = data.get("db")
                            break
                    except Exception as e: 
                        print(f"  [Warning] Parse error on line {line_idx+1}: {e}")
                        continue
            
            if detected_q:
                print(f"  [Detected] Question: \"{detected_q}\"")
                print(f"  [Detected] Database: {detected_db}")
                question = question or detected_q
                db_name = db_name or detected_db
                break # Found it!
            else:
                 print(f"  [Not Found] Instance '{instance_id}' not in this file.")
        
        if not detected_q:
            print(f"[Error] Could not find instance '{instance_id}' in any standard location.")
            sys.exit(1)

    if not question:
        print("[Error] No question provided. Use --question or --instance-id.")
        sys.exit(1)
    
    if not db_name:
        db_name = settings.DB_NAME or "public"

    # 2. Sequential ID Resolution
    sequential_id = get_next_instance_id(args.model)
    
    print(f"\n{'='*60}")
    print(f" 🧠 PHASE 2: RAG ANALYSIS EXECUTION")
    print(f" Result ID: {sequential_id} | Schema: {db_name}")
    print(f" Model: {args.model}")
    print(f"{'='*60}\n")

    # 3. Execution
    print(f"Question: \"{question}\"\n")
    
    execute_cmd = [
        sys.executable, "app/repos/scripts/run_single.py",
        "--question", question,
        "--db", db_name,
        "--use-rag",
        "--id", sequential_id,
        "--model", args.model
    ]
    
    if not run_command(execute_cmd):
        print("[Error] Analysis execution failed.")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f" ✅ ANALYSIS COMPLETE")
    print(f" Results Prefix: {sequential_id}")
    print(f" Log Path: app/repos/data/results/{args.model}/log/{sequential_id}.md")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
