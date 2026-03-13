import sys
import os
import json
from dotenv import load_dotenv
import argparse

from app.services.engines.llm_service import LLMService
from app.services.schemas.agent_state import AgentState
from app.services.engines.pipeline_service import run_analysis_pipeline
from app.services.utils.logger import Logger
from app.repositories.registry.paths import InstancePaths, SPIDER_DATASET, get_model_results_dir, initialize_directories
from app.repositories.config import settings

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="Run single text-to-SQL instance")
    parser.add_argument("--use-rag", action="store_true", help="Enable RAG retrieval")
    parser.add_argument("--id", type=str, required=False, help="Task ID to run")
    parser.add_argument("--input-jsonl", "--dataset", type=str, help="Dataset JSONL file")
    parser.add_argument("--question", type=str, help="Direct input question (overrides ID/JSONL search)")
    parser.add_argument("--model", type=str, default=settings.LLM_MODEL, help=f"Model name to use (default: {settings.LLM_MODEL})")
    parser.add_argument("--agents", type=str, default=None, help="Comma-separated list of agents to run (e.g. QueryPlanner,ContextEnrichment)")
    parser.add_argument("--results-dir", type=str, default=settings.RESULTS_DIR, help="Override results directory")
    parser.add_argument("--logs-dir", type=str, help="Override logs directory")
    parser.add_argument("--metadata-dir", type=str, default=settings.METADATA_DIR, help="Override metadata directory")
    parser.add_argument("--quiet", action="store_true", help="Minimal terminal output")
    args = parser.parse_args()
    
    # Enable binary logging to terminal
    Logger._verbose = True

    # Set up environment overrides if provided via CLI
    if args.results_dir: os.environ["RESULTS_DIR"] = args.results_dir
    if args.logs_dir: os.environ["LOGS_DIR"] = args.logs_dir
    if args.metadata_dir: os.environ["METADATA_DIR"] = args.metadata_dir

    load_dotenv()
    from app.repositories.registry.paths import get_next_instance_id, get_spider_dataset
    
    # Resolve dataset path dynamically
    current_input_jsonl = args.input_jsonl or str(get_spider_dataset())
    dataset_name = os.path.basename(current_input_jsonl)
    
    model_name = args.model or os.getenv("LLM_MODEL", "gpt-default")
    initialize_directories(model_name)
    target_id = args.id or get_next_instance_id(model_name)
    
    # Load task data
    task_data = None
    
    # Mode A: Direct Question
    if args.question:
        db_name = settings.SCHEMA
        print(f"[Running Direct Query]: DB: {db_name} | Model: {model_name} | RAG: {args.use_rag}", flush=True)
        task_data = {
            "question": args.question,
            "db": db_name,
            "instance_id": target_id
        }
    # Mode B: Search JSONL by ID
    elif args.id:
        print(f"[Running]: {target_id} | Input: {current_input_jsonl} | Model: {model_name} | RAG: {args.use_rag}", flush=True)
        if os.path.exists(current_input_jsonl):
            with open(current_input_jsonl, 'r', encoding='utf-8') as f:
                for line in f:
                    t = json.loads(line)
                    if t.get("instance_id") == target_id:
                        task_data = t
                        break
    else:
        print("[Error]: You must provide either --question or --id.", flush=True)
        return
                    
    if not task_data:
        if args.id:
            print(f"[Error]: Task {target_id} not found in {current_input_jsonl}", flush=True)
        else:
            print("[Error]: Failed to gather task data.", flush=True)
        return

    # Parse agents list
    enabled_agents = args.agents.split(",") if args.agents else None

    # Run Pipeline
    print("[Pipeline]: Starting...", flush=True)
    state = run_analysis_pipeline(
        question=task_data['question'],
        db_name=task_data.get('db'),
        dataset_name=dataset_name,
        instance_id=target_id,
        model_name=model_name,
        enabled_agents=enabled_agents,
        use_rag=args.use_rag,
        verbose=not args.quiet
    )
    
    is_fatal = state.error_message and "ERROR:" in state.error_message.upper() if state else True
    
    if is_fatal:
        print(f"[FAILED]: {state.error_message if state else 'Pipeline crashed'}", flush=True)
    else:
        print(f"[SUCCESS]: Results saved to results/{model_name.replace('/', '_')}/", flush=True)
    
    # Validation check for log file
    log_path = InstancePaths.log(target_id, model_name)
    if log_path.exists():
        print(f"[Log]: {log_path}", flush=True)
    else:
        print("[Warning]: Log file not found.", flush=True)

if __name__ == "__main__":
    main()
