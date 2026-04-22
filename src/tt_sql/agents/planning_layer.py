from typing import List
import json
from tt_sql.core.agent_base import BaseAgent, AgentState
from tt_sql.core.llm_service import LLMService
from tt_sql.core.prompt_loader import PromptLoader
from tt_sql.core.file_coordinator import FileCoordinator
import yaml
from tt_sql.core.paths import PIPELINE_CONFIG
from .input_layer import format_rag_columns, format_schema_to_str

class StepByStepPlannerAgent(BaseAgent):
    """
    Generates a high-level plan for answering the user query.
    """
    def __init__(self, llm_service: LLMService, config: dict = None):
        super().__init__(name="QueryPlanner", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        # Load configuration
        with open(PIPELINE_CONFIG, 'r') as f:
            pipeline_cfg = yaml.safe_load(f)
            labels = pipeline_cfg.get("labels", {})
            defaults = pipeline_cfg.get("defaults", {})

        roadmap_label = labels.get("planning_roadmap", "Execution Roadmap")
        self.log(state, f"PLAN_CATEGORY: {roadmap_label}")
        
        
        # Reconstruct intent context
        intent_context = f"Intent: {state.query_intent}, Complexity: {state.complexity_score}"
        
        # Schema Context Selection: Use RAG columns if available, otherwise fallback to full schema_info
        if state.rag_columns:
            schema_str = format_rag_columns(state.rag_columns)
        elif state.schema_info:
            schema_str = format_schema_to_str(state.schema_info)
        else:
            schema_str = "No schema info available."

        # Use in-memory inputs
        messages = self.prompt_loader.load_prompt(
            "query_planner",
            user_query=state.user_query,
            schema=schema_str,
            intent_path=intent_context,
            agent_role=self.role,
            agent_task=self.task
        )
                    
        response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
        if response and "step_by_step_approach" in response:
            state.step_by_step_plan = response["step_by_step_approach"]
            
            # Write plan to results/plan/ for traceability
            self.file_coordinator.write_plan(state.instance_id, state.step_by_step_plan, state.model_name)
        else:
            state.step_by_step_plan = defaults.get("fallback_plan", ["Analyze Schema", "Generate SQL"])
            
        self.log(state, f"Generated execution plan with {len(state.step_by_step_plan)} sub-tasks:")
        step_prefix = labels.get("planning_step_prefix", "PLAN_STEP: - ")
        for step in state.step_by_step_plan:
            self.log(state, f"{step_prefix}{step}")
        return state


