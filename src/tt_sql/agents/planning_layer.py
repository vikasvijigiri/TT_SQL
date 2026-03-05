from typing import List
import json
from ..core.agent_base import BaseAgent, AgentState
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.file_coordinator import FileCoordinator
from .input_layer import format_rag_columns

class StepByStepPlannerAgent(BaseAgent):
    """
    Generates a high-level plan for answering the user query.
    """
    def __init__(self, llm_service: LLMService):
        super().__init__(name="QueryPlanner")
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        self.log(state, "PLAN_CATEGORY: Execution Roadmap")
        
        
        # Reconstruct intent context
        intent_data = {
            "intent": state.query_intent,
            "complexity": state.complexity_score
        }
        intent_context = json.dumps(intent_data, indent=2)
        
        # Format raw RAG columns directly for the planner prompt
        schema_str = format_rag_columns(state.rag_columns) if state.rag_columns else "No RAG schema available."

        # Use in-memory inputs
        messages = self.prompt_loader.load_prompt(
            "query_planner",
            user_query=state.user_query,
            intent_path=intent_context
        )
                    
        response = self.llm.get_json_completion(messages, state=state)
        if response and "step_by_step_approach" in response:
            state.step_by_step_plan = response["step_by_step_approach"]
            
            # Write plan to results/plan/ for traceability
            self.file_coordinator.write_plan(state.instance_id, state.step_by_step_plan, state.model_name)
        else:
            state.step_by_step_plan = ["Analyze Schema", "Generate SQL"]
            
        self.log(state, f"Generated execution plan with {len(state.step_by_step_plan)} sub-tasks:")
        for step in state.step_by_step_plan:
            self.log(state, f"PLAN_STEP: - {step}")
        return state


