import json
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.app.core.observability.token_budget import token_budget_enforcer
from agent.blackboard.run_blackboard import get_blackboard

class MetaReasonerOutput(BaseModel):
    known_facts: str = Field(..., description="Summary of what is currently known.")
    missing_evidence: str = Field(..., description="Summary of what is missing based on the goal.")
    unverified_assumptions: str = Field(..., description="List of assumptions that need verifying.")
    best_next_action: str = Field(..., description="Recommended next action (e.g., SCHEMA_LINKING, EXECUTING, ANSWERING)")
    overall_confidence: float = Field(..., description="Confidence score from 0.0 to 1.0 that the goal can be met with current state.")

class MetaReasonerAgent:
    """
    Evaluates the blackboard and decides what the Orchestrator should do next.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.assembler = PromptAssembler(stage="META_REASONING")
        self.agent_name = "META_REASONER"

    def reason(self, user_query: str) -> MetaReasonerOutput:
        logger.set_agent(self.agent_name)
        bb = get_blackboard()
        logger.info(f"Meta-Reasoner analyzing current blackboard state...")

        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=None,
            intent=None
        )

        blackboard_state = bb.format_for_prompt()
        full_user_prompt = assembled.user_prompt.replace("{BLACKBOARD_STATE}", blackboard_state)

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
            output = MetaReasonerOutput(**data)
            
            # Update blackboard confidence
            bb.confidence["answer"] = output.overall_confidence
            
            logger.log_parsed_data("Meta Reasoning", output)
            return output
        except Exception as e:
            logger.error(f"Failed to parse MetaReasoner output: {e}")
            return MetaReasonerOutput(
                known_facts="Parse error",
                missing_evidence="Parse error",
                unverified_assumptions="Parse error",
                best_next_action="CONTINUE",
                overall_confidence=bb.confidence["answer"]
            )
