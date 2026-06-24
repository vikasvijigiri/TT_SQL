import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.telemetry.token_budget import token_budget_enforcer
from agent.blackboard.run_blackboard import get_blackboard
from agent.blackboard.dynamic_rules import FailureMemory
from agent.validators.deterministic_validators import DeterministicValidators

class SemanticPlannerOutput(BaseModel):
    goal: str = Field(..., description="Brief description of the goal")
    required_facts: List[str] = Field(default_factory=list, description="Specific facts needed")
    required_entities: List[str] = Field(default_factory=list, description="Entities needed")
    required_metrics: List[str] = Field(default_factory=list, description="Metrics needed")
    required_documents: List[str] = Field(default_factory=list, description="Knowledge documents needed")
    answer_strategy: str = Field(..., description="The high level strategy to get the answer")

class SemanticPlannerAgent:
    """
    Executes AFTER analysis but BEFORE schema linking to determine WHAT facts are needed.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.assembler = PromptAssembler(stage="SEMANTIC_PLANNING")
        self.agent_name = "SEMANTIC_PLANNER"

    def plan(self, user_query: str) -> SemanticPlannerOutput:
        logger.set_agent(self.agent_name)
        logger.info(f"Planning semantic strategy for: {user_query}")

        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=None,
            intent=None
        )

        response, metrics = self.llm_client.generate(
            system_prompt=assembled.system_prompt,
            user_prompt=assembled.user_prompt
        )

        logger.record_agent_telemetry(
            agent_name=self.agent_name,
            tokens_in=metrics.get("input_tokens", 0),
            tokens_out=metrics.get("output_tokens", 0),
            latency_ms=metrics.get("latency_ms", 0),
            confidence=1.0,
        )

        token_budget_enforcer.check_budget(
            self.agent_name, 
            metrics.get("input_tokens", 0) + metrics.get("output_tokens", 0)
        )

        try:
            # Clean response
            clean_resp = response.strip()
            if clean_resp.startswith("```json"):
                clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp[:-3]
                
            data = json.loads(clean_resp.strip())
            output = SemanticPlannerOutput(**data)
            
            # Deterministic Validation Gate
            val_result = DeterministicValidators.validate_plan(output)
            if not val_result.is_valid:
                FailureMemory.record_failure(
                    failure_type="Validation Rejection (Plan)",
                    root_cause=val_result.rejection_reason or "Unknown",
                    impact="Semantic plan is incomplete.",
                    prevention_rule="Always provide a concrete goal and explicit required facts in the semantic plan."
                )
                raise ValueError(f"Plan validation failed: {val_result.rejection_reason}")
            
            # Write to Blackboard
            bb = get_blackboard()
            bb.goal = output.goal
            bb.required_facts = output.required_facts
            bb.required_entities = output.required_entities
            bb.required_metrics = output.required_metrics
            bb.required_documents = output.required_documents
            bb.answer_strategy = output.answer_strategy
            
            logger.log_parsed_data("Semantic Plan", output)
            return output
        except Exception as e:
            logger.error(f"Failed to parse SemanticPlanner output: {e}")
            # Fallback
            return SemanticPlannerOutput(
                goal="Unknown",
                required_facts=[],
                required_entities=[],
                required_metrics=[],
                required_documents=[],
                answer_strategy="direct_sql"
            )
