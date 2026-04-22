import time
from typing import Optional, List, Dict, Any
from app.schemas.agent_state import AgentState
from app.core.logging.logger import Logger
from app.infrastructure.external.llm import LLMService

from app.domain.agents.planner import PlannerAgent
from app.domain.agents.coder import CoderAgent
from app.domain.agents.executor import ExecutorAgent
from app.domain.agents.reviewer import ReviewerAgent

class AnalysisPipeline:
    """
    Orchestrates the sequential execution of AI agents for Text-to-SQL.
    Maintains the state and manages the iterative refinement loop.
    """
    
    def __init__(self, model_name: str, user_slug: str, project_slug: str):
        self.user_slug = user_slug
        self.project_slug = project_slug
        self.llm = LLMService(model=model_name)
        
        # Initialize Domain Agents
        self.planner = PlannerAgent(user_slug=user_slug, project_slug=project_slug)
        self.coder = CoderAgent(llm=self.llm, user_slug=user_slug, project_slug=project_slug)
        self.executor = ExecutorAgent(user_slug=user_slug, project_slug=project_slug)
        self.reviewer = ReviewerAgent(llm=self.llm, user_slug=user_slug, project_slug=project_slug)

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        Logger.log(f"--- Starting Analysis Pipeline: {state.instance_id} ---")
        start_time = time.time()

        try:
            # 1. Enrichment Phase
            if not getattr(state, "stop_requested", False):
                Logger.log_section("Context Enrichment")
                state = self.planner.run(state, on_token=on_token)

            # 2. Iterative Refinement Loop (Max 3 attempts)
            for i in range(3):
                if getattr(state, "stop_requested", False): break
                
                Logger.log_section(f"SQL Generation & Execution (Attempt {i+1})")
                
                # Generate
                state = self.coder.run(state, on_token=on_token)
                if "ERROR" in state.chosen_query: break
                
                # Execute
                state = self.executor.run(state)
                
                # Review
                state = self.reviewer.run(state)
                if state.is_result_valid:
                    self.planner.log(state, "Critique passed. Result is valid.")
                    break
                else:
                    self.planner.log(state, f"Critique failed. Refinement required: {state.critic_feedback}", level="WARNING")

            # 3. Final Summary (Handled by orchestrator calling Summary agent or similar)
            # For now, we return the state after the loop
            
        except Exception as e:
            Logger.log(f"Pipeline Critical Failure: {e}", level="ERROR")
            state.error_message = str(e)
        finally:
            state.total_duration = time.time() - start_time
            Logger.log(f"--- Pipeline Completed in {state.total_duration:.2f}s ---")
            
        return state
