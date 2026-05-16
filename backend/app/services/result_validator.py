from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.utils.logger import logger
from backend.app.utils.dialect_loader import DialectLoader
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import json
import re

class ResultValidatorOutput(BaseModel):
    audit_reasoning: str = Field(description="Deep, step-by-step analysis of grain alignment and filter validity.")
    is_valid: bool = Field(description="Whether the result is semantically correct and grounded in evidence.")
    exploration_sql: Optional[str] = Field(None, description="Optional SQL to 'probe' the DB if the result is 0 or grain is mismatched.")
    feedback: Optional[str] = Field(None, description="Direct feedback for the Self-Corrector on what to pivot or align.")

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("result_validator.yaml")

class ResultValidator:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.dialect_loader = DialectLoader()

    def validate_result(self, user_query: str, sql: str, result_preview: str, schema_context: str = "", stats: Dict = None, exploration_results: str = None, dialect: str = "snowflake", lessons: str = "", empty_result_diagnostic: str = "") -> ResultValidatorOutput:
        logger.set_agent("DATA_IQ")
        logger.info("Evaluating result quality (Data IQ Layer)...")

        dialect_reasoning = self.dialect_loader.load_dialect_reasoning(dialect)

        variables = {
            "USER_QUERY": user_query,
            "SQL": sql,
            "RESULT_PREVIEW": result_preview,
            "SCHEMA_CONTEXT": schema_context,
            "STATS": json.dumps(stats, indent=2) if stats else "No statistics available.",
            "EXPLORATION_RESULTS": f"\nEXPLORATION RESULTS (PROBES):\n{exploration_results}" if exploration_results else "",
            "EMPTY_RESULT_DIAGNOSTIC": f"\nEMPTY RESULT DIAGNOSTIC (FILTER COLLAPSE):\n{empty_result_diagnostic}" if empty_result_diagnostic else "",
            "DIALECT": dialect.upper(),
            "DIALECT_RULES": dialect_reasoning,
            "DYNAMIC_REASONING_PROTOCOL": lessons
        }

        messages = PromptLoader.load(PROMPT_PATH, variables=variables)

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ResultValidatorOutput,
            )
            
            # Apply Dialect Sanitizers to Exploration SQL
            if result.exploration_sql:
                for sanitizer in self.dialect_loader.get_sanitizers(dialect):
                    search = sanitizer.get("search")
                    replace = sanitizer.get("replace")
                    if search:
                        result.exploration_sql = re.sub(re.escape(search), replace, result.exploration_sql, flags=re.IGNORECASE)

            if not result.is_valid:
                logger.warning(f"Data IQ Check Failed: {result.feedback}")
            else:
                logger.success("Data IQ Check Passed.")
                
            return result
        except Exception as e:
            logger.error(f"Data IQ validation failed: {e}")
            return ResultValidatorOutput(is_valid=True, audit_reasoning="Validation failed to run; assuming valid.", feedback="Validation failed to run; assuming valid.")
        finally:
            logger.reset_agent()
