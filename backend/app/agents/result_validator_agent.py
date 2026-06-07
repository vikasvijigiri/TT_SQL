from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.utils.logger import logger
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.core.dialects.rule_retriever import DialectRuleRetriever
from backend.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever
from pydantic import BaseModel, Field, AliasChoices
from typing import Optional, Dict, List
import json
import re

class ResultValidatorOutput(BaseModel):
    audit_reasoning: str = Field(validation_alias=AliasChoices("audit_reasoning", "reasoning", "thought_process", "analysis", "thought"), description="Deep, step-by-step analysis of grain alignment and filter validity.")
    is_valid: bool = Field(description="Whether the result is semantically correct and grounded in evidence.")
    exploration_sql: Optional[str] = Field(None, description="Optional SQL to 'probe' the DB if the result is 0 or grain is mismatched.")
    feedback: Optional[str] = Field(None, description="Direct feedback for the Self-Corrector on what to pivot or align.")

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("result_validator.yaml")

class ResultValidatorAgent:
    def __init__(self, llm_client: LLMClient, semantic_engine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.dialect_loader = DialectLoader()

    def validate_result(self, user_query: str, sql: str, result_preview: str, schema_context: str = "", stats: Dict = None, exploration_results: str = None, dialect: str = "snowflake", lessons: str = "", empty_result_diagnostic: str = "", relevant_tables: Optional[List[str]] = None, table_columns: Optional[Dict[str, List[str]]] = None, intent=None) -> ResultValidatorOutput:
        logger.set_agent("DATA_IQ")
        logger.info("Evaluating result quality (Data IQ Layer)...")

        # Reuse pre-computed intent from orchestrator to avoid redundant analysis
        if intent is None:
            intent = HierarchicalRetriever().analyze_intent(user_query)
        
        stats_str = json.dumps(stats, indent=2) if stats else "No statistics available."
        exp_str = f"\nEXPLORATION RESULTS (PROBES):\n{exploration_results}" if exploration_results else ""
        diag_str = f"\nEMPTY RESULT DIAGNOSTIC (FILTER COLLAPSE):\n{empty_result_diagnostic}" if empty_result_diagnostic else ""
        
        combined_lessons = (
            f"TARGET SQL:\n```sql\n{sql}\n```\n\n"
            f"RESULT PREVIEW:\n{result_preview}\n\n"
            f"STATS:\n{stats_str}\n{exp_str}\n{diag_str}\n\n"
            f"PAST LESSONS:\n{lessons}"
        )

        from backend.app.core.prompts.prompt_assembler import PromptAssembler
        assembler = PromptAssembler(dialect=dialect, stage="DATA_IQ")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="RESULT_VALIDATOR",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            lessons=combined_lessons
        )

        system_prompt = assembled.system_prompt
        user_prompt   = assembled.user_prompt

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
