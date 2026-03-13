from typing import List
import json
from app.services.agents.base import BaseAgent
from app.services.schemas.agent_state import AgentState
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.services.utils.logger import Logger
from app.repositories.persistence.file_coordinator import FileCoordinator
from app.services.agents.input_layer import format_rag_columns

class StepByStepPlannerAgent(BaseAgent):
    """
    StepByStepPlannerAgent is responsible for generating a logical execution roadmap
    based on the user's query and the retrieved schema context. It serves as the 
    architect of the analysis pipeline.
    """
    def __init__(self, llm_service: LLMService, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="QueryPlanner", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir)

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        """
        Executes the planning phase by analyzing query intent and schema context.
        
        Args:
            state (AgentState): The current state of the analysis pipeline.
            on_token (callable, optional): Callback for real-time token streaming.
            
        Returns:
            AgentState: The updated state with a step-by-step execution plan.
        """
        self.log(state, "PLAN_CATEGORY: Execution Roadmap")
        
        try:
            # Reconstruct intent context
            intent_data = {
                "intent": state.query_intent,
                "complexity": state.complexity_score
            }
            intent_context = json.dumps(intent_data, indent=2)
            
            # Resolve schema context for the planner
            if state.schema_info:
                schema_str = self.file_coordinator._format_schema_as_markdown(state.schema_info)
            elif state.rag_columns:
                from .input_layer import format_rag_columns
                schema_str = format_rag_columns(state.rag_columns)
            else:
                schema_str = "No RAG schema available yet (Planning Phase)."

            # Load and format planning prompt
            messages = self.prompt_loader.load_prompt(
                "query_planner",
                user_query=state.user_query,
                intent_path=intent_context,
                schema=schema_str
            )
                        
            response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
            
            plan_steps = []
            if response and "step_by_step_approach" in response:
                plan_steps = response["step_by_step_approach"]
            
            if not plan_steps:
                self.log(state, "No plan steps found in LLM response. Using default fallback.", level="WARNING")
                plan_steps = ["Analyze Schema Context", "Generate SQL Candidates", "Execute and Validate Results"]
    
            # Persist plan to state
            state.step_by_step_plan = plan_steps
            
            # Log successful plan generation
            self.log(state, f"Generated execution plan with {len(state.step_by_step_plan)} sub-tasks:")
            for step in state.step_by_step_plan:
                self.log(state, f"PLAN_STEP: - {step}")
                
        except Exception as e:
            self.log(state, f"Planning Adjustment: {str(e)}", level="WARNING")
            state.step_by_step_plan = ["Analyze Schema", "Generate SQL Query"]
            
        return state
