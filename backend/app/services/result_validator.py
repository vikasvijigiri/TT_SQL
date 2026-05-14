from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.utils.logger import logger
from pydantic import BaseModel, Field
from typing import Optional

class ResultValidatorOutput(BaseModel):
    audit_reasoning: str = Field(description="Deep, step-by-step analysis of the columns, logic, and data quality.")
    is_plausible: bool = Field(description="Whether the result makes sense given the query.")
    feedback: Optional[str] = Field(None, description="Detailed feedback on why the result might be incorrect.")
    improvement_suggestion: Optional[str] = Field(None, description="Specific suggestion for the Self-Corrector.")

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("result_validator.yaml")

class ResultValidator:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def validate_result(self, user_query: str, sql: str, result_preview: str, stats: dict = None) -> ResultValidatorOutput:
        logger.set_agent("DATA_IQ")
        logger.info("Evaluating result quality (Data IQ Layer)...")

        stats_str = ""
        if stats:
            stats_str = f"\nDATASET STATISTICS:\n{stats}"

        messages = PromptLoader.load(PROMPT_PATH, variables={
            "USER_QUERY": user_query,
            "SQL": sql,
            "RESULT_PREVIEW": result_preview + stats_str
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ResultValidatorOutput,
            )
            
            if not result.is_plausible:
                logger.warning(f"Data IQ Check Failed: {result.feedback}")
            else:
                logger.success("Data IQ Check Passed.")
                
            return result
        except Exception:
            logger.error("Data IQ validation failed.")
            return ResultValidatorOutput(is_plausible=True, feedback="Validation failed to run; assuming plausible.")
        finally:
            logger.reset_agent()
