import os
import sys
import argparse
from dotenv import load_dotenv

# Add src to path
from app.services.agents.execution_layer import SQLiteExecutorAgent, PostgresExecutorAgent
from app.services.schemas.agent_state import AgentState

def test_executor():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Test DB Executor")
    parser.add_argument("--db-type", type=str, choices=["sqlite", "postgres"], default="sqlite", help="DB type")
    parser.add_argument("--sql", type=str, default="SELECT 1", help="SQL to execute")
    args = parser.parse_args()

    db_name = settings.SCHEMA
    print(f"Testing {args.db_type} executor on: {db_name}")
    
    state = AgentState(user_query="Test", db_path="", db_name=db_name)
    state.chosen_query = args.sql
    
    try:
        if args.db_type == "sqlite":
            executor = SQLiteExecutorAgent()
        else:
            executor = PostgresExecutorAgent()
            
        state = executor.run(state)
        
        if state.execution_result and not state.execution_result.error_message:
            print("âœ… Execution Successful")
            print(f"Rows: {state.execution_result.row_count}")
            print(f"Columns: {state.execution_result.columns}")
        else:
            print(f"âŒ Execution Failed: {state.execution_result.error_message if state.execution_result else 'No result'}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_executor()
