import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.telemetry.token_budget import token_budget_enforcer
from agent.blackboard.dynamic_rules import FailureMemory
from agent.validators.deterministic_validators import DeterministicValidators
from agent.contracts.schemas import SchemaLinkerOutput

class JoinPlanOutput(BaseModel):
    joins: List[str] = Field(description="Explicit JOIN ON clauses (e.g., 'tableA JOIN tableB ON tableA.id = tableB.a_id')")
    tables_in_graph: List[str] = Field(description="All tables successfully connected in this join graph")
    reasoning: str = Field(description="Explanation of the join path chosen")

class JoinPlannerAgent:
    """
    Executes AFTER the SchemaLinker.
    Plans the explicit join graph connecting the selected tables to prevent 
    cartesian products and hallucinated relationships.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.assembler = PromptAssembler(stage="JOIN_PLANNER")
        self.agent_name = "JOIN_PLANNER"

    def plan_joins(self, user_query: str, linked_schema: SchemaLinkerOutput, schema_context: str) -> JoinPlanOutput:
        logger.set_agent(self.agent_name)
        
        # Fast path: if 0 or 1 tables are selected, no joins are needed.
        if len(linked_schema.selected_tables) <= 1:
            logger.info("Only 1 table selected. Skipping Join Planner.")
            return JoinPlanOutput(joins=[], tables_in_graph=linked_schema.selected_tables, reasoning="Single table.")

        logger.info(f"Planning join graph for tables: {linked_schema.selected_tables}")

        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=schema_context,
            intent=None
        )

        user_prompt = assembled.user_prompt.replace("{SELECTED_TABLES}", str(linked_schema.selected_tables))

        response, metrics = self.llm_client.generate(
            system_prompt=assembled.system_prompt,
            user_prompt=user_prompt
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
            clean_resp = response.strip()
            if clean_resp.startswith("```json"):
                clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp[:-3]
                
            data = json.loads(clean_resp.strip())
            output = JoinPlanOutput(**data)
            
            # Deterministic Validation Gate
            val_result = DeterministicValidators.validate_join_plan(output, linked_schema.selected_tables)
            if not val_result.is_valid:
                FailureMemory.record_failure(
                    failure_type="Validation Rejection (Join Plan)",
                    root_cause=val_result.rejection_reason or "Unknown",
                    impact="Potential Cartesian Product or broken join graph.",
                    prevention_rule="Ensure all selected tables are connected via explicit PK/FK relationships."
                )
                raise ValueError(f"Join Plan validation failed: {val_result.rejection_reason}")

            logger.log_parsed_data("Join Plan", output)
            return output
            
        except Exception as e:
            logger.error(f"Failed to parse or validate JoinPlan output: {e}")
            raise e
