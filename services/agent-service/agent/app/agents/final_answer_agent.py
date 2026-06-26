import json
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.app.core.observability.token_budget import token_budget_enforcer

class FinalAnswerOutput(BaseModel):
    final_answer: str = Field(..., description="The strictly formatted final answer")

class FinalAnswerAgent:
    """
    Executes as the very last step. Formats the final answer string.
    NO reasoning, NO sql, just formatting.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.assembler = PromptAssembler(stage="FINAL_ANSWER")
        self.agent_name = "FINAL_ANSWER"

    def format_answer(self, user_query: str, synthesized_evidence: str) -> str:
        logger.set_agent(self.agent_name)
        logger.info(f"Formatting final answer for query: {user_query}")

        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=None,
            intent=None
        )

        full_user_prompt = assembled.user_prompt.replace("{SYNTHESIZED_EVIDENCE}", synthesized_evidence)

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

        final_answer = response.strip()
        
        # Remove any surrounding markdown tags if the model output them
        if final_answer.startswith("```") and final_answer.endswith("```"):
            lines = final_answer.splitlines()
            if len(lines) >= 3:
                final_answer = "\n".join(lines[1:-1]).strip()

        logger.info(f"Final Answer: {final_answer}")
        return final_answer
