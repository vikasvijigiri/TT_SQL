from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from backend.app.core.pipeline_config import PipelineModeConfig, LIGHTWEIGHT_CONFIG, BALANCED_CONFIG, DEEP_REASONING_CONFIG
from backend.app.core.prompts.compression_pipeline import CompressionPipeline, CompressedPromptOutput
from backend.app.core.retrieval.hierarchical_retriever import QueryIntentAnalysis
from backend.app.models.schemas import SemanticContext
from backend.app.utils.logger import logger

class ExperimentResultComparison(BaseModel):
    experiment_name: str
    query: str
    config_a_name: str
    config_b_name: str
    tokens_a: int
    tokens_b: int
    token_diff_percent: float
    relevance_score_a: float
    relevance_score_b: float
    dropped_sections_a: List[str]
    dropped_sections_b: List[str]

class PromptExperimentManager:
    """
    Enterprise Prompt A/B Experimentation Engine.
    Executes parallel prompt compilations across differing configurations (e.g., compact vs verbose)
    to benchmark token savings, section retention, and relevance density.
    """
    
    @classmethod
    def run_experiment(
        cls,
        experiment_name: str,
        query: str,
        sys_template: str,
        schema_context: SemanticContext,
        relevant_tables: List[str],
        table_columns_map: Dict[str, List[str]],
        rules: List[str],
        templates: List[Dict[str, str]],
        intent: QueryIntentAnalysis,
        config_a: PipelineModeConfig = BALANCED_CONFIG,
        config_b: PipelineModeConfig = LIGHTWEIGHT_CONFIG,
        config_a_name: str = "Balanced (A)",
        config_b_name: str = "Lightweight (B)"
    ) -> ExperimentResultComparison:
        logger.info(f"[PromptExperiment] Running A/B Prompt Experiment: '{experiment_name}'...")
        
        pipe_a = CompressionPipeline(config=config_a, stage="EXPERIMENT_A")
        out_a = pipe_a.execute(query, sys_template, schema_context, relevant_tables, table_columns_map, rules, templates, intent)
        
        pipe_b = CompressionPipeline(config=config_b, stage="EXPERIMENT_B")
        out_b = pipe_b.execute(query, sys_template, schema_context, relevant_tables, table_columns_map, rules, templates, intent)
        
        diff = 0.0
        if out_a.total_tokens > 0:
            diff = ((out_b.total_tokens - out_a.total_tokens) / out_a.total_tokens) * 100.0

        comp = ExperimentResultComparison(
            experiment_name=experiment_name,
            query=query,
            config_a_name=config_a_name,
            config_b_name=config_b_name,
            tokens_a=out_a.total_tokens,
            tokens_b=out_b.total_tokens,
            token_diff_percent=round(diff, 2),
            relevance_score_a=out_a.summary.relevance_score,
            relevance_score_b=out_b.summary.relevance_score,
            dropped_sections_a=out_a.summary.dropped_sections,
            dropped_sections_b=out_b.summary.dropped_sections
        )

        logger.info(
            f"[PromptExperiment][{experiment_name}] Summary:\n"
            f"  * {config_a_name}: ~{out_a.total_tokens} tokens | Relevance: {out_a.summary.relevance_score}\n"
            f"  * {config_b_name}: ~{out_b.total_tokens} tokens | Relevance: {out_b.summary.relevance_score}\n"
            f"  * Token Difference: {diff:+.2f}%"
        )
        return comp
