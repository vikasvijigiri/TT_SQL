from typing import List, Dict, Optional
from pydantic import BaseModel
from backend.app.utils.logger import logger


class PromptTelemetrySummary(BaseModel):
    stage_name: str
    total_prompt_tokens: int
    system_prompt_tokens: int
    user_prompt_tokens: int
    section_token_counts: Dict[str, int]
    dropped_sections: List[str]
    retained_sections: List[str]
    compression_ratio: float
    deduplication_savings_tokens: int
    relevance_score: float
    execution_mode: str

    # Task 14 Extended Enterprise Telemetry
    raw_tokens: Optional[int] = 0
    post_dedup_tokens: Optional[int] = 0
    post_render_tokens: Optional[int] = 0
    final_sent_tokens: Optional[int] = 0
    template_savings: Optional[int] = 0
    schema_savings: Optional[int] = 0
    directive_savings: Optional[int] = 0


class PromptTelemetryLogger:
    """
    Enterprise Prompt Observability Engine.
    Captures granular telemetry on prompt construction, section token distributions,
    deduplication savings, and compression efficiency across all pipeline stages.
    """

    @classmethod
    def log_telemetry(cls, summary: PromptTelemetrySummary) -> None:
        """Outputs structured telemetry info to the enterprise logger."""
        dropped_str = (
            f" | Dropped Sections: {summary.dropped_sections}"
            if summary.dropped_sections
            else " | No Dropped Sections"
        )
        logger.info(
            f"[PromptTelemetry][{summary.stage_name}] Mode: {summary.execution_mode} | Final Sent Tokens: {summary.final_sent_tokens or summary.total_prompt_tokens} "
            f"(Sys: {summary.system_prompt_tokens}, User: {summary.user_prompt_tokens}) | "
            f"Comp Ratio: {summary.compression_ratio:.2f}x | Global Savings: {summary.deduplication_savings_tokens} tokens | "
            f"Rel Score: {summary.relevance_score:.2f}{dropped_str}"
        )
        if (
            summary.template_savings
            or summary.directive_savings
            or summary.schema_savings
        ):
            logger.debug(
                f"[PromptTelemetry][{summary.stage_name}] Savings Breakdown -> "
                f"Templates: {summary.template_savings} | Directives: {summary.directive_savings} | Schema: {summary.schema_savings}"
            )
        for sec, cnt in summary.section_token_counts.items():
            logger.debug(
                f"[PromptTelemetry][{summary.stage_name}] Section '{sec}': ~{cnt} tokens contribution"
            )
