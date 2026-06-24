import os
from typing import List, Dict
from pydantic import BaseModel
from agent.orchestration.pipeline_config import PipelineModeConfig, BALANCED_CONFIG
from agent.app.core.prompts.compression_pipeline import CompressionPipeline
from agent.app.core.prompting.context_scorer import ContextQualityScorer
from agent.app.core.dialects.rule_retriever import DialectRuleRetriever
from agent.app.core.query_analysis.capability_detector import QueryCapabilityDetector
from agent.app.core.context.confidence_estimator import ConfidenceEstimator
from agent.app.core.prompting.adaptive_budgeting import AdaptiveBudgetManager
from agent.contracts.schemas import SemanticContext
from agent.app.core.retrieval.hierarchical_retriever import QueryIntentAnalysis
from agent.services.logger import logger
from agent.services.prompt_loader import PromptLoader
from agent.app.core.config import PROMPTS_DIR


class AssembledPrompt(BaseModel):
    system_prompt: str
    user_prompt: str
    total_tokens: int
    quality_score: float
    dropped_sections: List[str]


class PromptAssembler:
    """
    Enterprise Surgical Prompt Assembly Engine.
    Coordinates compact system prompt loading, query capability profiling,
    confidence estimation, adaptive budgeting, dynamic rule retrieval, and the 6-stage
    CompressionPipeline while strictly enforcing token ceilings and relevance quality scoring.
    """

    def __init__(
        self,
        config: PipelineModeConfig = BALANCED_CONFIG,
        dialect: str = "snowflake",
        stage: str = "DEFAULT",
    ):
        self.config = config
        self.dialect = dialect.lower()
        self.stage = stage.upper()
        self.pipeline = CompressionPipeline(
            config=config, stage=self.stage, dialect=self.dialect
        )
        self.rule_retriever = DialectRuleRetriever(dialect=self.dialect)
        self.scorer = ContextQualityScorer()

    def _load_compact_system_prompt(self, agent_type: str) -> str:
        mapping = {
            "SCHEMA_LINKER": "schema_linker.yaml",
            "SQL_GENERATOR": "sql_generator.yaml",
            "SELF_CORRECTOR": "self_corrector.yaml",
            "TABLE_PRUNER": "table_pruner.yaml",
            "COLUMN_PRUNER": "column_pruner.yaml",
            "DATA_IQ": "result_validator.yaml",
            "RESULT_VALIDATOR": "result_validator.yaml",
            "CRITIC": "critic.yaml",
        }

        filename = mapping.get(agent_type.upper(), "sql_generator.yaml")
        filepath = os.path.join(PROMPTS_DIR, filename)

        if os.path.exists(filepath):
            try:
                content = PromptLoader.system(filepath)
                if content:
                    return content.strip()
            except Exception as e:
                logger.warning(f"[PromptAssembler] Failed to read {filepath}: {e}")

        return f"You are a high-precision enterprise {agent_type} agent. Your task is to analyze the database schema and query to output the required JSON structure."

    def assemble(
        self,
        user_query: str,
        agent_type: str,
        context: SemanticContext,
        intent: QueryIntentAnalysis,
        relevant_tables: List[str] | None = None,
        table_columns: Dict[str, List[str]] | None = None,
        lessons: str = "",
        error_history: str = "",
    ) -> AssembledPrompt:
        logger.debug(
            f"[PromptAssembler] Assembling surgical prompt for agent '{agent_type}'..."
        )

        # 1. Load Surgical System Prompt Directives
        sys_prompt = self._load_compact_system_prompt(agent_type)

        # 2. Query Capability Detection (Task 2)
        profile = QueryCapabilityDetector.detect(user_query, intent, context)

        # 3. Confidence Estimation (Task 5)
        confidence = ConfidenceEstimator.estimate(user_query, context, intent, profile)

        # 4. Adaptive Token Budgeting (Task 13)
        budget = AdaptiveBudgetManager.calculate_budget(agent_type, user_query, profile)

        # 5. Retrieve Adaptive Rule Families & Syntax Templates (Task 1, 9, 11)
        raw_config = self.rule_retriever._load_raw_config()
        raw_templates = raw_config.get("examples", [])
        adaptive_rules = self.rule_retriever.get_adaptive_rules(profile, max_rules=25)

        # 6. Execute 6-Stage Compression Pipeline
        comp_out = self.pipeline.execute(
            user_query=user_query,
            system_prompt_template=sys_prompt,
            raw_schema_context=context,
            relevant_table_names=relevant_tables,
            table_columns_map=table_columns,
            raw_dialect_rules=adaptive_rules,
            raw_templates=raw_templates,
            intent=intent,
            past_lessons=lessons,
            error_history=error_history,
            profile=profile,
            confidence=confidence,
            custom_ceiling=budget["total_ceiling"],
        )

        # 7. Context Quality Evaluation
        total_cols = (
            sum(len(t.columns) for t in context.tables)
            if (context and context.tables)
            else 1
        )
        rel_cols = (
            sum(len(cols) for cols in table_columns.values())
            if table_columns
            else total_cols
        )

        eval_res = self.scorer.evaluate_prompt(
            user_query, comp_out.user_prompt, total_cols, rel_cols
        )
        if not eval_res.is_acceptable:
            logger.warning(
                f"[PromptAssembler] Context quality flagged (Score: {eval_res.total_score}). {eval_res.rejection_reason}"
            )

        logger.info(
            f"[PromptAssembler] Surgical prompt assembled successfully (~{comp_out.total_tokens} tokens, Quality: {eval_res.total_score})."
        )

        return AssembledPrompt(
            system_prompt=comp_out.system_prompt,
            user_prompt=comp_out.user_prompt,
            total_tokens=comp_out.total_tokens,
            quality_score=eval_res.total_score,
            dropped_sections=comp_out.summary.dropped_sections,
        )
