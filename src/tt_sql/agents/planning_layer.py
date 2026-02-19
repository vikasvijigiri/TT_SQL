from typing import List
import json
from ..core.agent_base import BaseAgent, AgentState
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.file_coordinator import FileCoordinator

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
        
        self.log(state, "PLAN_CATEGORY: ⚡ Execution Roadmap")
        
        
        # Reconstruct intent context
        intent_data = {
            "intent": state.query_intent,
            "complexity": state.complexity_score
        }
        intent_context = json.dumps(intent_data, indent=2)
        
        # Reconstruct enriched context
        context_data = {
            "relevant_tables": state.relevant_tables,
            "reasoning": state.context_reasoning
        }
        context_context = json.dumps(context_data, indent=2)
        
        # Use in-memory inputs
        messages = self.prompt_loader.load_prompt(
            "query_planner",
            user_query=state.user_query,
            intent_path=intent_context,
            context_path=context_context
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

class RelationshipGraphBuilderAgent(BaseAgent):
    """
    Builds a graph of table relationships (PK/FK).
    """
    def __init__(self):
        super().__init__(name="RelationshipGraphBuilder")

    def run(self, state: AgentState) -> AgentState:
        # State already has schema info with FKs from SchemaAnalyzer
        # This agent would enhance it by inferring missing links or visualizing
        
        # For this MVP, we just pass. 
        # Future: use networkx or similar to build a graph object and store in state
        self.log(state, "Relationship graph implicit in schema info.")
        return state
