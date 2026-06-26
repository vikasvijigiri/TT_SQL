import json
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.app.core.observability.token_budget import token_budget_enforcer
from agent.blackboard.run_blackboard import get_blackboard
from agent.app.models.schemas import SchemaDiscoveryOutput
from agent.app.services.semantic_engine import SemanticContextEngine

class SchemaDiscoveryAgent:
    """
    Executes BEFORE the SchemaLinker.
    Scans the entire database schema context to identify macro-level domains,
    table subsets, and relationship paths relevant to the user query.
    """
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm_client = llm_client
        self.semantic_engine = semantic_engine
        self.assembler = PromptAssembler(stage="SCHEMA_DISCOVERY")
        self.agent_name = "SCHEMA_DISCOVERY"

    def discover(self, user_query: str) -> SchemaDiscoveryOutput:
        logger.set_agent(self.agent_name)
        bb = get_blackboard()
        logger.info(f"Discovering relevant schema domains for query: {user_query}")

        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=self.semantic_engine.context,
            intent=None
        )

        blackboard_context = ""
        if bb.goal:
            blackboard_context = f"\nGoal: {bb.goal}\nRequired Entities: {bb.required_entities}\n"

        full_user_prompt = assembled.user_prompt.replace("{BLACKBOARD_CONTEXT}", blackboard_context)

        response, metrics = self.llm_client.generate(
            system_prompt=assembled.system_prompt,
            user_prompt=full_user_prompt
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
            output = SchemaDiscoveryOutput(**data)
            
            logger.log_parsed_data("Discovered Schema", output)
            return output
        except Exception as e:
            logger.error(f"Failed to parse SchemaDiscovery output: {e}")
            return SchemaDiscoveryOutput(
                discovered_domains=[],
                relevant_tables=[],
                known_relationships=[],
                reasoning=f"Parse Error: {e}"
            )
