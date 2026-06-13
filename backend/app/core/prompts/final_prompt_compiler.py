from typing import List, Dict, Tuple, Optional
from backend.app.core.prompts.prompt_ast import PromptAST, PromptNode
from backend.app.core.prompts.normalization_pipeline import PromptNormalizationPipeline
from backend.app.core.prompts.global_deduplicator import GlobalPromptDeduplicator
from backend.app.core.prompts.rule_canonicalizer import RuleCanonicalizer
from backend.app.core.prompts.template_canonicalizer import TemplateCanonicalizer
from backend.app.core.prompts.responsibility_splitter import (
    PromptResponsibilitySplitter,
)
from backend.app.core.prompts.directive_compactor import DirectiveCompactor
from backend.app.core.prompts.lesson_overlap_resolver import LessonRuleOverlapResolver
from backend.app.core.tokenization.final_tokenizer import FinalTokenizer
from backend.app.core.prompts.final_budget_enforcer import FinalBudgetEnforcer
from backend.app.core.observability.prompt_telemetry import (
    PromptTelemetryLogger,
    PromptTelemetrySummary,
)
from backend.app.core.prompts.boundary_manager import PromptBoundaryManager
from backend.app.core.prompts.reasoning_depth_controller import ReasoningDepthController
from backend.app.core.quality.prompt_quality_guard import PromptQualityGuard
from backend.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from backend.app.utils.logger import logger


class FinalPromptCompilerOutput:
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


class FinalPromptCompiler:
    """
    Enterprise Final Prompt Compilation Engine.
    Executes the true post-render compilation lifecycle:
    assemble_sections() -> deduplicate() -> render() -> final_compress() -> tokenize() -> enforce_budget().
    """

    def __init__(
        self, stage: str = "DEFAULT", dialect: str = "snowflake", mode: str = "balanced"
    ):
        self.stage = stage.upper()
        self.dialect = dialect.lower()
        self.mode = mode.lower()

    def normalize_prompt_text(self, text: str) -> str:
        return PromptNormalizationPipeline.normalize(text)

    def compile_system_prompt(self, raw_system_prompt: str, user_query: str) -> str:
        clean_sys, _ = PromptBoundaryManager.enforce_boundaries(
            raw_system_prompt, "", user_query, dialect=self.dialect
        )
        return self.normalize_prompt_text(clean_sys)

    def deduplicate_global_sections(
        self, ast: PromptAST, system_prompt: str
    ) -> Tuple[PromptAST, int]:
        sys_keys = PromptResponsibilitySplitter.extract_system_keys(system_prompt)
        global_seen = set(sys_keys)
        total_savings = 0

        for node in ast.root_nodes:
            if node.name in ("dialect_rules", "reasoning_directives"):
                clean_text, savings = (
                    GlobalPromptDeduplicator.deduplicate_section_content(
                        node.render(), global_seen, similarity_threshold=0.85
                    )
                )
                node.content = clean_text
                total_savings += savings

        for node in ast.root_nodes:
            if node.name in ("past_lessons", "syntax_templates"):
                clean_text, savings = (
                    GlobalPromptDeduplicator.deduplicate_section_content(
                        node.render(), global_seen, similarity_threshold=0.85
                    )
                )
                node.content = clean_text
                total_savings += savings

        return ast, total_savings

    def enforce_final_budget(
        self, ast: PromptAST, system_tokens: int, custom_cap: int | None = None
    ) -> Tuple[PromptAST, List[str]]:
        return FinalBudgetEnforcer.enforce_budget(
            ast, system_tokens, stage=self.stage, custom_cap=custom_cap
        )

    def compile_user_prompt(self, ast: PromptAST, user_query: str) -> str:
        sections_text = ast.render_all(separator="\n\n")
        final_user_prompt = f"{sections_text}\n\n=== USER QUERY ===\n<user_query>\n{user_query.strip()}\n</user_query>"
        return final_user_prompt.strip()

    def compile(
        self,
        user_query: str,
        raw_system_prompt: str,
        compressed_schema_text: str,
        raw_rules: List[str],
        selected_templates: List[Dict[str, str]],
        raw_directives: str,
        past_lessons: str = "",
        error_history: str = "",
        compression_ratio: float = 1.0,
        raw_schema_tokens: int = 1000,
        profile: Optional[QueryCapabilityProfile] = None,
        domain: str = "General Enterprise",
        custom_cap: Optional[int] = None,
    ) -> FinalPromptCompilerOutput:
        logger.debug(
            f"[FinalPromptCompiler][{self.stage}] Starting TRUE final prompt compilation..."
        )

        if not profile:
            profile = QueryCapabilityProfile()

        # 1. Compile System Prompt via Boundary Manager
        sys_prompt = self.compile_system_prompt(raw_system_prompt, user_query)
        sys_tokens = FinalTokenizer.count_system_tokens(sys_prompt)

        raw_user_approx = sum(
            max(1, len(str(x)) // 4)
            for x in (
                compressed_schema_text,
                raw_rules,
                selected_templates,
                raw_directives,
                past_lessons,
                user_query,
            )
        )
        raw_total_tokens = sys_tokens + raw_user_approx

        # 2. Canonicalize & Deduplicate Core Inputs
        clean_rules, rule_sav = RuleCanonicalizer.canonicalize_and_deduplicate(
            raw_rules
        )
        rules_text = f"=== {self.dialect.upper()} DIALECT RULES ===\n" + "\n".join(
            f"- {r}" for r in clean_rules
        )

        clean_templates, tmpl_sav = TemplateCanonicalizer.canonicalize_templates(
            selected_templates
        )
        templates_text = TemplateCanonicalizer.format_canonical_templates(
            clean_templates
        )

        # Dynamic Reasoning Depth
        active_directives = ReasoningDepthController.get_directives(
            user_query, profile, domain=domain, dialect=self.dialect
        )
        clean_directives, dir_sav = DirectiveCompactor.compact_directives(
            "\n".join(active_directives)
        )

        clean_lessons, less_sav = LessonRuleOverlapResolver.resolve_overlap(
            past_lessons, clean_rules, clean_directives
        )
        if clean_lessons:
            clean_lessons = f"=== PAST LESSONS & KNOWLEDGE ===\n{clean_lessons}"

        schema_sav = max(
            0, raw_schema_tokens - max(1, len(compressed_schema_text) // 4)
        )
        global_savings = rule_sav + tmpl_sav + dir_sav + less_sav + schema_sav

        # 3. Construct Prompt AST
        ast = PromptAST()
        ast.add_node(
            PromptNode(
                section_type="rules",
                name="dialect_rules",
                content=rules_text,
                priority=2,
                droppable=False,
                semantic_value=0.95,
            )
        )
        ast.add_node(
            PromptNode(
                section_type="directives",
                name="reasoning_directives",
                content=clean_directives,
                priority=2,
                droppable=False,
                semantic_value=0.95,
            )
        )

        if templates_text:
            ast.add_node(
                PromptNode(
                    section_type="templates",
                    name="syntax_templates",
                    content=templates_text,
                    priority=4,
                    droppable=True,
                    semantic_value=0.85,
                )
            )
        if clean_lessons:
            ast.add_node(
                PromptNode(
                    section_type="lessons",
                    name="past_lessons",
                    content=clean_lessons,
                    priority=3,
                    droppable=True,
                    semantic_value=0.80,
                )
            )
        if error_history and len(error_history.strip()) > 5:
            ast.add_node(
                PromptNode(
                    section_type="metadata",
                    name="error_history",
                    content=f"=== EXECUTION ERROR HISTORY ===\n{error_history}",
                    priority=1,
                    droppable=False,
                    semantic_value=1.0,
                )
            )

        # 4. Normalize AST Content
        for node in ast.root_nodes:
            node.content = self.normalize_prompt_text(node.render())

        # 5. Global Deduplication across AST Nodes & System Prompt
        ast, post_dedup_sav = self.deduplicate_global_sections(ast, sys_prompt)
        global_savings += post_dedup_sav

        post_dedup_user_prompt = self.compile_user_prompt(ast, user_query)
        post_dedup_tokens = sys_tokens + FinalTokenizer.count_user_tokens(
            post_dedup_user_prompt
        )

        # 6. Enforce Hard Token Budgets & Quality Guard
        trimmed_ast, dropped_names = self.enforce_final_budget(
            ast, sys_tokens, custom_cap=custom_cap
        )
        trimmed_ast.root_nodes = PromptQualityGuard.audit_and_safeguard(
            trimmed_ast.root_nodes, profile, dropped_names, dialect=self.dialect
        )

        # 7. Render Final User Prompt and Prepend Schema to System Prompt for Caching
        final_user_prompt = self.compile_user_prompt(trimmed_ast, user_query)
        sys_prompt = f"=== DATABASE SCHEMA ===\n{compressed_schema_text}\n\n{sys_prompt}"

        token_counts = FinalTokenizer.tokenize_final_prompt(
            sys_prompt, final_user_prompt
        )
        final_sent_tokens = token_counts["total_tokens"]

        sec_counts = {
            node.name: FinalTokenizer.count_user_tokens(node.render())
            for node in trimmed_ast.root_nodes
        }
        retained_names = [node.name for node in trimmed_ast.root_nodes]

        avg_rel = sum(node.semantic_value for node in trimmed_ast.root_nodes) / max(
            1, len(trimmed_ast.root_nodes)
        )

        summary = PromptTelemetrySummary(
            stage_name=self.stage,
            total_prompt_tokens=final_sent_tokens,
            system_prompt_tokens=token_counts["system_tokens"],
            user_prompt_tokens=token_counts["user_tokens"],
            section_token_counts=sec_counts,
            dropped_sections=dropped_names,
            retained_sections=retained_names,
            compression_ratio=round(compression_ratio, 2),
            deduplication_savings_tokens=global_savings,
            relevance_score=round(avg_rel, 2),
            execution_mode=self.mode,
            raw_tokens=raw_total_tokens,
            post_dedup_tokens=post_dedup_tokens,
            post_render_tokens=final_sent_tokens,
            final_sent_tokens=final_sent_tokens,
            template_savings=tmpl_sav,
            schema_savings=schema_sav,
            directive_savings=dir_sav,
        )

        PromptTelemetryLogger.log_telemetry(summary)

        return FinalPromptCompilerOutput(
            system_prompt=sys_prompt,
            user_prompt=final_user_prompt,
            total_tokens=final_sent_tokens,
            summary=summary,
        )
