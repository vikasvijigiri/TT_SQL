from agent.services.llm import LLMClient

from agent.services.logger import logger

from agent.app.utils.dialect_loader import DialectLoader

from agent.app.utils.prompt_loader import PromptLoader

from agent.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever

from pydantic import BaseModel, Field, AliasChoices

from typing import Optional, Dict, List

import json

import re




class ResultValidatorOutput(BaseModel):

    audit_reasoning: Optional[str] = Field(
        None,
        validation_alias=AliasChoices(
            "audit_reasoning", "reasoning", "thought_process", "analysis", "thought"
        ),
        description="Deep, step-by-step analysis of grain alignment and filter validity.",
    )

    is_valid: bool = Field(
        description="Whether the result is semantically correct and grounded in evidence."
    )

    confidence_score: Optional[float] = Field(
        None,
        description="Confidence in the result's correctness, 0.0-1.0. 1.0 = certain, 0.0 = highly suspect.",
    )

    exploration_sql: Optional[str] = Field(
        None,
        description="Optional SQL to 'probe' the DB if the result is 0 or grain is mismatched.",
    )

    feedback: Optional[str] = Field(
        None,
        description="Direct feedback for the Self-Corrector on what to pivot or align.",
    )




from agent.app.core.config import get_prompt_path


PROMPT_PATH = get_prompt_path("result_validator.yaml")




class ResultValidatorAgent:

    def __init__(self, llm_client: LLMClient, semantic_engine):

        self.llm = llm_client

        self.semantic_engine = semantic_engine

        self.dialect_loader = DialectLoader()


    def validate_result(
        self,
        user_query: str,
        sql: str,
        result_preview: str,
        schema_context: str = "",
        stats: Dict | None = None,
        exploration_results: str | None = None,
        dialect: str = "snowflake",
        lessons: str = "",
        empty_result_diagnostic: str = "",
        relevant_tables: Optional[List[str]] = None,
        table_columns: Optional[Dict[str, List[str]]] = None,
        intent=None,
    ) -> ResultValidatorOutput:

        logger.set_agent("DATA_IQ")

        logger.info("Evaluating result quality (Data IQ Layer)...")


        # Reuse pre-computed intent from orchestrator to avoid redundant analysis

        if intent is None:

            intent = HierarchicalRetriever().analyze_intent(user_query)


        stats_str = json.dumps(stats, indent=2) if stats else "No statistics available."

        # Use assembler ONLY for the system prompt — it prepends the compressed schema
        # context and the validator instructions. The user prompt is built directly from
        # the yaml template so that {SQL}, {RESULT_PREVIEW}, and {STATS} each appear in
        # their own clearly-labelled section. Previously everything was bundled into
        # combined_lessons → {PAST_LESSONS}, causing the LLM to report "Cannot perform
        # validation without a result set" even when the query returned rows.

        from agent.app.core.prompts.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(dialect=dialect, stage="DATA_IQ")

        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="RESULT_VALIDATOR",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            lessons="",  # schema/rules live in system_prompt; result lives in user_prompt below
        )

        system_prompt = assembled.system_prompt

        # Dialect rules (may be empty if no dialect YAML is configured, which is fine
        # since the schema is already in system_prompt from the assembler).
        dialect_rules = self.dialect_loader.load_dialect_reasoning(dialect)

        # Directly substitute every placeholder in the yaml user template so the LLM
        # always sees SQL, result preview, and stats in their proper labelled sections.
        user_prompt = PromptLoader.user(
            PROMPT_PATH,
            variables={
                "DIALECT": dialect.upper(),
                "DIALECT_RULES": dialect_rules or "(see system prompt)",
                "USER_QUERY": user_query,
                "SQL": sql,
                "RESULT_PREVIEW": result_preview,
                "STATS": stats_str,
                "SCHEMA_CONTEXT": schema_context or "",
                "EXPLORATION_RESULTS": exploration_results or "",
                "EMPTY_RESULT_DIAGNOSTIC": empty_result_diagnostic or "",
                "PAST_LESSONS": lessons or "",
            },
        )

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

                        result.exploration_sql = re.sub(
                            re.escape(search),
                            replace,
                            result.exploration_sql,
                            flags=re.IGNORECASE,
                        )


            if not result.is_valid:

                logger.warning(f"Data IQ Check Failed: {result.feedback}")

            else:

                logger.success("Data IQ Check Passed.")


            return result

        except Exception as e:

            logger.error(f"Data IQ validation failed: {e}")

            # Default to is_valid=False on exception — silently passing invalid results
            # would suppress SELF_CORRECTOR and allow wrong answers through.

            return ResultValidatorOutput(  # type: ignore
                is_valid=False,
                audit_reasoning="Validation encountered an error and could not confirm result correctness.",
                feedback="Validation failed to run; please regenerate the SQL with a different approach.",
            )

        finally:

            logger.reset_agent()
