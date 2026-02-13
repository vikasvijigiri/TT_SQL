import sys
import os
import json
import csv
from dotenv import load_dotenv

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from tt_sql.core.orchestrator import Orchestrator
from tt_sql.core.state import AgentState
from tt_sql.core.llm_service import LLMService
from tt_sql.core.logger import Logger

# Agents
from tt_sql.agents.input_layer import (
    SQLiteFileLoaderAgent, 
    SchemaAnalyzerAgent, 
    QueryIntentClassifierAgent, 
    ContextEnrichmentAgent
)
from tt_sql.agents.planning_layer import (
    StepByStepPlannerAgent, 
    RelationshipGraphBuilderAgent
)
from tt_sql.agents.generation_layer import MultiCandidateGeneratorAgent
from tt_sql.agents.loop_layer import RefinementLoopAgent

def main():
    load_dotenv()
    
    # Initialize Markdown Logger
    Logger.set_log_file("run_log.md")
    Logger.log_section("Batch Runner Started")
    
    # 1. Setup paths
    # Assuming batch_runner.py is in src/
    base_dir = os.path.dirname(os.path.dirname(__file__)) # Project root
    jsonl_path = os.path.join(base_dir, "spider2-lite.jsonl")
    results_dir = os.path.join(base_dir, "results")
    sql_results_dir = os.path.join(results_dir, "sql")
    csv_results_dir = os.path.join(results_dir, "csv")
    schema_results_dir = os.path.join(results_dir, "schema")
    
    os.makedirs(sql_results_dir, exist_ok=True)
    os.makedirs(csv_results_dir, exist_ok=True)
    os.makedirs(schema_results_dir, exist_ok=True)
    
    # 2. Initialize Services & Agents (Reusable)
    llm_service = LLMService()
    
    agents = [
        SQLiteFileLoaderAgent(),
        SchemaAnalyzerAgent(),
        QueryIntentClassifierAgent(llm_service),
        ContextEnrichmentAgent(llm_service),
        RelationshipGraphBuilderAgent(),
        StepByStepPlannerAgent(llm_service),
        RefinementLoopAgent(llm_service)
    ]
    
    orchestrator = Orchestrator(agents)
    
    # 3. Read JSONL
    Logger.log(f"Reading from {jsonl_path}")
    tasks = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
                
    Logger.log(f"Found {len(tasks)} tasks.")
    
    # 4. Processing Loop
    for i, task in enumerate(tasks):
        instance_id = task.get("instance_id")
        db_name = task.get("db") # e.g., "IPL"
        question = task.get("question")
        
        if not instance_id or not db_name or not question:
            print(f"Skipping invalid task line {i}")
            continue
            
        # Construct DB Path
        # Pattern: C:/Users/VikasVijigiri/Documents/Spider2/spider2-lite/resource/databases/spider2-localdb/{DB}.sqlite
        db_path = f"C:/Users/VikasVijigiri/Documents/Spider2/spider2-lite/resource/databases/spider2-localdb/{db_name}.sqlite"
        
        # Check existence
        if not os.path.exists(db_path):
            Logger.log(f"[{i+1}/{len(tasks)}] Skipping: DB not found at {db_path}", level="WARN")
            # Optional: Write a specific failure file?
            continue
            
        Logger.log_section(f"[{i+1}/{len(tasks)}] Processing {instance_id} (DB: {db_name})")
        try:
            # Create Initial State
            initial_state = AgentState(
                user_query=question,
                db_path=db_path,
                instance_id=instance_id
            )
            
            # Run Pipeline
            final_state = orchestrator.run_pipeline(initial_state)
            
            # Save Results
            
            # 1. SQL File
            sql_out_path = os.path.join(sql_results_dir, f"{instance_id}.sql")
            generated_sql = final_state.chosen_query or "-- No SQL Generated"
            Logger.log(f"Final SQL for {instance_id}:")
            Logger.log_code(generated_sql)
            
            with open(sql_out_path, 'w', encoding='utf-8') as f_sql:
                f_sql.write(generated_sql)
                
            # 2. CSV Results File
            csv_out_path = os.path.join(csv_results_dir, f"{instance_id}.csv")
            if final_state.execution_result and final_state.execution_result.rows:
                Logger.log(f"Execution successful. Rows: {len(final_state.execution_result.rows)}")
                with open(csv_out_path, 'w', newline='', encoding='utf-8') as f_csv:
                    writer = csv.writer(f_csv)
                    # Write headers if available
                    if final_state.execution_result.columns:
                        writer.writerow(final_state.execution_result.columns)
                    writer.writerows(final_state.execution_result.rows)
            else:
                 # Create empty CSV or write error info
                 err_msg = final_state.execution_result.error_message if final_state.execution_result else "No result object"
                 Logger.log(f"Execution failed or empty. Error: {err_msg}", level="WARN")
                 with open(csv_out_path, 'w', newline='', encoding='utf-8') as f_csv:
                     writer = csv.writer(f_csv)
                     # Write error header
                     writer.writerow(["status", "error"])
                     writer.writerow(["failed", err_msg])

            Logger.log(f"Saved results for {instance_id}")

        except Exception as e:
            Logger.log(f"CRITICAL ERROR processing {instance_id}: {e}", level="ERROR")
            # Continue to next task
            continue

if __name__ == "__main__":
    main()
