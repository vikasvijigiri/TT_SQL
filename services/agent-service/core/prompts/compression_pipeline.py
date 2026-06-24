from typing import List, Dict, Optional
from agent.orchestration.pipeline_config import PipelineModeConfig, BALANCED_CONFIG
from agent.app.core.prompting.token_budget_manager import TokenBudgetManager
from agent.app.core.dialects.rule_deduplicator import RuleDeduplicator
from agent.app.core.schema.sample_suppressor import SampleSuppressor
from agent.app.core.prompts.semantic_template_retriever import (
    SemanticTemplateRetriever,
)
from agent.app.core.prompts.adaptive_compression_engine import (
    AdaptiveCompressionEngine,
)
from agent.app.core.context.confidence_estimator import ConfidenceMetrics
from agent.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from agent.app.core.prompts.reasoning_directives import ReasoningDirectives
from agent.app.core.prompts.final_prompt_compiler import FinalPromptCompiler
from agent.app.core.context.context_relevance import ContextRelevanceScorer
from agent.telemetry.prompt_telemetry import PromptTelemetrySummary
from agent.app.core.retrieval.hierarchical_retriever import QueryIntentAnalysis
from agent.contracts.schemas import SemanticContext
from agent.services.logger import logger


class CompressedPromptOutput:
    def __init__(
        self,
        system_prompt: str,
        user_prompt: str,
        total_tokens: int,
        summary: PromptTelemetrySummary,
    ):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.total_tokens = total_tokens
        self.summary = summary


class CompressionPipeline:
    """
    Enterprise Prompt Compression & Token Orchestration Pipeline.
    Executes surgical schema compression and delegates final prompt compilation,
    canonicalization, global deduplication, and budget enforcement to FinalPromptCompiler.
    """

    def __init__(
        self,
        config: PipelineModeConfig = BALANCED_CONFIG,
        stage: str = "DEFAULT",
        dialect: str = "snowflake",
    ):
        self.config = config
        self.stage = stage.upper()
        self.dialect = dialect.lower()
        self.deduplicator = RuleDeduplicator()
        self.scorer = ContextRelevanceScorer()
        self.budget_manager = TokenBudgetManager(config, stage=self.stage)

    def execute(
        self,
        user_query: str,
        system_prompt_template: str,
        raw_schema_context: SemanticContext,
        relevant_table_names: Optional[List[str]],
        table_columns_map: Optional[Dict[str, List[str]]],
        raw_dialect_rules: List[str],
        raw_templates: List[Dict[str, str]],
        intent: QueryIntentAnalysis,
        past_lessons: str = "",
        error_history: str = "",
        profile: Optional[QueryCapabilityProfile] = None,
        confidence: Optional[ConfidenceMetrics] = None,
        custom_ceiling: Optional[int] = None,
    ) -> CompressedPromptOutput:
        logger.debug(
            f"[CompressionPipeline][{self.stage}] Starting surgical prompt compression and compilation..."
        )

        if not profile:
            profile = QueryCapabilityProfile()
        if not confidence:
            from agent.app.core.context.confidence_estimator import (
                ConfidenceEstimator,
            )

            confidence = ConfidenceEstimator.estimate(
                user_query, raw_schema_context, intent, profile
            )

        domain = intent.inferred_domain if intent else "General Enterprise"

        # Adaptive Template Selection
        selected_templates = SemanticTemplateRetriever.retrieve_templates(
            user_query,
            domain,
            profile,
            max_templates=2 if self.config.mode != "lightweight" else 1,
        )

        # Adaptive Compression Policy
        policy = AdaptiveCompressionEngine.get_policy(user_query, confidence, profile)

        # Surgical Schema Construction & Sample Value Suppression
        schema_lines = []
        raw_schema_chars = 0

        tables_to_format = [
            t
            for t in raw_schema_context.tables
            if not relevant_table_names
            or any(
                rt.lower().replace('"', "") in t.name.lower().replace('"', "")
                for rt in relevant_table_names
            )
        ]

        for t in tables_to_format:
            raw_schema_chars += len(t.name) + sum(
                len(c.name) + sum(len(str(v)) for v in c.sample_values)
                for c in t.columns
            )
            schema_lines.append(f"Table: {t.name}")
            if t.description:
                desc = t.description[: policy.max_schema_description_len]
                schema_lines.append(f"Description: {desc}")

            cols_to_include = t.columns
            if table_columns_map:
                t_clean = t.name.replace('"', "").split(".")[-1].lower()
                for m_tbl, m_cols in table_columns_map.items():
                    if m_tbl.replace('"', "").split(".")[-1].lower() == t_clean:
                        m_clean_cols = [c.replace('"', "").lower() for c in m_cols]
                        cols_to_include = [
                            c
                            for c in t.columns
                            if c.name.replace('"', "").split(".")[-1].lower()
                            in m_clean_cols
                        ]
                        break

            for c in cols_to_include:
                c_str = f"  - {c.name} ({c.type})"
                if c.description:
                    c_desc = c.description[: policy.max_schema_description_len]
                    c_str += f": {c_desc}"
                if c.nested_keys:
                    c_str += f" | Variant Keys: {', '.join(c.nested_keys)}"

                if policy.include_raw_sample_rows:
                    samples = SampleSuppressor.smart_sample_selection(
                        c, max_samples=policy.max_sample_values_per_col
                    )
                    if samples:
                        c_str += f" | Samples: [{', '.join(samples)}]"

                schema_lines.append(c_str)
            schema_lines.append("")  # Table separator

        evidence_notes = []
        if (
            profile.requires_timestamps
            or profile.requires_aggregation
            or profile.requires_windows
        ):
            interesting_tokens = (
                "date",
                "year",
                "month",
                "time",
                "cpc",
                "symbol",
                "level",
            )
            for t in tables_to_format:
                for c in t.columns:
                    col_name = c.name.lower()
                    if (
                        any(token in col_name for token in interesting_tokens)
                        and c.sample_values
                    ):
                        sample_preview = ", ".join(str(v) for v in c.sample_values[:3])
                        evidence_notes.append(
                            f"{t.name}.{c.name}: samples -> {sample_preview}"
                        )

        if evidence_notes:
            evidence_block = "=== SAMPLE EVIDENCE HINTS ===\n" + "\n".join(
                f"- {line}" for line in evidence_notes[:20]
            )
            past_lessons = (
                f"{past_lessons}\n\n{evidence_block}".strip()
                if past_lessons
                else evidence_block
            )

        compressed_schema_text = "\n".join(schema_lines).strip()
        raw_schema_tokens = max(1, raw_schema_chars // 4)
        comp_schema_tokens = self.budget_manager.estimate_tokens(compressed_schema_text)
        compression_ratio = round(
            max(1.0, raw_schema_tokens / max(1, comp_schema_tokens)), 2
        )

        compiler = FinalPromptCompiler(
            stage=self.stage, dialect=self.dialect, mode=self.config.mode
        )
        raw_directives = ReasoningDirectives.get_all_directives(
            dialect=self.dialect,
            include_sqlite_time_series=(
                self.dialect == "sqlite"
                and (
                    profile.requires_windows
                    or profile.requires_timestamps
                    or profile.requires_aggregation
                )
            ),
        )

        final_out = compiler.compile(
            user_query=user_query,
            raw_system_prompt=system_prompt_template,
            compressed_schema_text=compressed_schema_text,
            raw_rules=raw_dialect_rules,
            selected_templates=selected_templates,
            raw_directives=raw_directives,
            past_lessons=past_lessons if policy.preserve_past_lessons else "",
            error_history=error_history,
            compression_ratio=compression_ratio,
            raw_schema_tokens=raw_schema_tokens,
            profile=profile,
            domain=domain,
            custom_cap=custom_ceiling,
        )

        return CompressedPromptOutput(
            system_prompt=final_out.system_prompt,
            user_prompt=final_out.user_prompt,
            total_tokens=final_out.total_tokens,
            summary=final_out.summary,
        )
