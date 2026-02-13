import sys
import os
import json
from dotenv import load_dotenv

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from tt_sql.core.orchestrator import Orchestrator
from tt_sql.core.state import AgentState
from tt_sql.core.llm_service import LLMService

# Agents
from tt_sql.agents.input_layer import *
from tt_sql.agents.planning_layer import *
from tt_sql.agents.generation_layer import *
from tt_sql.agents.execution_layer import *

def main():
    load_dotenv()
    
    # Setup
    base_dir = os.path.dirname(os.path.dirname(__file__))
    jsonl_path = os.path.join(base_dir, "spider2-lite.jsonl")
    
    target_id = "local010"
    task = None
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if target_id in line:
                t = json.loads(line)
                if t["instance_id"] == target_id:
                    task = t
                    break
    
    if not task:
        print("Task not found")
        return

    print("Task:", task)
    db_name = task["db"]
    db_path = f"C:/Users/VikasVijigiri/Documents/Spider2/spider2-lite/resource/databases/spider2-localdb/{db_name}.sqlite"
    
    # Init Pipeline
    llm_service = LLMService()
    agents = [
        SQLiteFileLoaderAgent(),
        SchemaAnalyzerAgent(),
        QueryIntentClassifierAgent(llm_service),
        ContextEnrichmentAgent(llm_service),
        RelationshipGraphBuilderAgent(),
        StepByStepPlannerAgent(llm_service),
        MultiCandidateGeneratorAgent(llm_service),
        SQLiteExecutorAgent(),
        ErrorRefinerAgent(llm_service),
        ResultValidatorAgent()
    ]
    orchestrator = Orchestrator(agents)
    
    state = AgentState(
        user_query=task["question"],
        db_path=db_path
    )
    
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write("\n--- RUNNING PIPELINE ---\n")
        final = orchestrator.run_pipeline(state)
        
        f.write("\n--- LOGS ---\n")
        for log in final.logs:
            f.write(log + "\n")
            
        f.write("\n--- RESULT ---\n")
        if final.execution_result and final.execution_result.error_message:
             f.write(f"Error: {final.execution_result.error_message}\n")
        elif final.execution_result:
             f.write(f"Rows: {len(final.execution_result.rows)}\n")
        else:
             f.write("No execution result\n")
        f.write(f"Chosen Query: {final.chosen_query}\n")

if __name__ == "__main__":
    main()
