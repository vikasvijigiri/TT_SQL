import os
import sys
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path BEFORE any app.* imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.logger import Logger
from app.services.llm_service import LLMService
from app.models.agent_state import AgentState
from app.services.agents.planning_layer import StepByStepPlannerAgent
from app.services.agents.input_layer import ContextEnrichmentAgent
from app.services.agents.generation_layer import MultiCandidateGeneratorAgent as SQLBuilderAgent
from app.services.agents.critic_layer import CriticAgent as SQLCriticAgent
from app.services.agents.execution_layer import SQLiteExecutorAgent

def test_planner(llm):
    from app.models.config import settings
    agent = StepByStepPlannerAgent(llm)
    state = AgentState(
        instance_id="test_plan",
        user_query="How many users signed up last week?",
        db_path=f"resources/spider2-localdb/{settings.COLLECTION_NAME}.sqlite"
    )
    print(f"--- Testing {agent.name} ---")
    state = agent.run(state)
    print("Plan:", state.step_by_step_plan)

def test_builder(llm):
    from app.models.config import settings
    agent = SQLBuilderAgent(llm)
    state = AgentState(
        instance_id="test_sql",
        user_query="Show me orders over 100 dollars",
        db_path=f"resources/spider2-localdb/{settings.COLLECTION_NAME}.sqlite",
        step_by_step_plan=["Find orders where total_amount > 100", "Select all columns"],
        schema_info={"orders": {"columns": [{"column_name": "total_amount", "type": "numeric"}]}}
    )
    print(f"--- Testing {agent.name} ---")
    state = agent.run(state)
    print("SQL:", state.chosen_query)

def test_critic(llm):
    from app.models.config import settings
    agent = SQLCriticAgent(llm)
    state = AgentState(
        instance_id="test_critic",
        user_query="Show me orders over 100 dollars",
        db_path=f"resources/spider2-localdb/{settings.COLLECTION_NAME}.sqlite",
        chosen_query="SELECT * FROM orders WHERE total_amount > 100",
        schema_info={"orders": {"columns": [{"column_name": "total_amount", "type": "numeric"}]}}
    )
    print(f"--- Testing {agent.name} ---")
    state = agent.run(state)
    print("Feedback:", state.critic_feedback)

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Consolidated Agent Tester")
    parser.add_argument("agent", choices=["planner", "builder", "critic", "all"], help="Agent to test")
    parser.add_argument("--model", type=str, default=os.getenv("LLM_MODEL"), help="Model to use")
    args = parser.parse_args()

    llm = LLMService(model=args.model)
    
    if args.agent in ["planner", "all"]: test_planner(llm)
    if args.agent in ["builder", "all"]: test_builder(llm)
    if args.agent in ["critic", "all"]: test_critic(llm)

if __name__ == "__main__":
    main()
