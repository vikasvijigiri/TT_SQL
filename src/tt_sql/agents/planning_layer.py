from typing import List
from ..core.agent_base import BaseAgent, AgentState
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.file_coordinator import FileCoordinator

class StepByStepPlannerAgent(BaseAgent):
    """
    Generates a high-level plan for answering the user query.
    """
    def __init__(self, llm_service: LLMService):
        super().__init__(name="StepByStepPlanner")
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        self.log(state, "PLAN_CATEGORY: ⚡ Execution Roadmap")
        
        # Get paths
        intent_path = str(InstancePaths.intent(state.instance_id, state.model_name))
        context_path = str(InstancePaths.context(state.instance_id, state.model_name))
        
        # Use file-based inputs
        messages = self.prompt_loader.load_prompt(
            "query_planning",
            user_query=state.user_query,
            intent_path=f"file://{intent_path}",
            context_path=f"file://{context_path}"
        )
                    
        response = self.llm.get_json_completion(messages)
        if response and "step_by_step_approach" in response:
            state.step_by_step_plan = response["step_by_step_approach"]
            
            # Write plan to results/plan/
            self.file_coordinator.write_plan(state.instance_id, response, state.model_name)
            self.log(state, f"Plan written to results/plan/{state.instance_id}.json")
        else:
            state.step_by_step_plan = ["Analyze Schema", "Generate SQL"]
            
        self.log(state, f"Generated execution plan with {len(state.step_by_step_plan)} sub-tasks:")
        for i, step in enumerate(state.step_by_step_plan):
            self.log(state, f"PLAN_STEP: {i+6}. {step}")
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
