import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure src is in path to import tt_sql
sys.path.append(os.path.join(os.path.dirname(__file__)))

import argparse
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
    parser = argparse.ArgumentParser(description="Text-to-SQL Agentic System")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--query", required=True, help="Natural language query")
    args = parser.parse_args()

    # Initialize Markdown Logger
    Logger.set_log_file("run_log.md")
    Logger.log_section("Single Query Run Started")

    # 1. Initialize Services
    llm_service = LLMService()

    # 2. Instantiate Agents
    agents = [
        SQLiteFileLoaderAgent(),
        SchemaAnalyzerAgent(),
        QueryIntentClassifierAgent(llm_service),
        ContextEnrichmentAgent(llm_service),
        RelationshipGraphBuilderAgent(),
        StepByStepPlannerAgent(llm_service),
        RefinementLoopAgent(llm_service)
    ]

    # 3. Setup Orchestrator
    orchestrator = Orchestrator(agents)

    # 4. Create Initial State
    initial_state = AgentState(
        user_query=args.query,
        db_path=args.db
    )

    # 5. Run Pipeline
    Logger.log(f"Processing query: '{args.query}' on DB: '{args.db}'")
    final_state = orchestrator.run_pipeline(initial_state)

    # 6. Output Results
    Logger.log_section("FINAL RESULTS")
    
    if final_state.execution_result and final_state.execution_result.error_message:
        Logger.log(f"Error: {final_state.execution_result.error_message}", level="ERROR")
    elif final_state.execution_result:
        Logger.log(f"Query:")
        Logger.log_code(final_state.chosen_query)
        Logger.log(f"Columns: {final_state.execution_result.columns}")
        Logger.log(f"Rows ({final_state.execution_result.row_count}):")
        sample_rows = str(final_state.execution_result.rows[:10])
        Logger.log(sample_rows)
        if final_state.execution_result.row_count > 10:
            Logger.log("... (more rows truncated)")
    else:
        Logger.log("No execution result.", level="WARN")

    print("\nLogs:")
    for log in final_state.logs:
        print(log)

if __name__ == "__main__":
    main()
