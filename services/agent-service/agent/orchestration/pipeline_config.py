from pydantic import BaseModel, Field
from typing import Literal


class PipelineModeConfig(BaseModel):
    mode: Literal["lightweight", "balanced", "deep_reasoning"] = "balanced"
    max_tables_per_query: int = Field(
        default=15,
        description="Maximum number of candidate tables retrieved for a query.",
    )
    max_columns_per_table: int = Field(
        default=25,
        description="Maximum number of candidate columns retrieved per table.",
    )
    schema_compression_level: Literal["aggressive", "balanced", "verbose"] = Field(
        default="balanced", description="Level of schema compaction."
    )
    token_budget_limit: int = Field(
        default=25000, description="Max token limit enforced by TokenBudgetManager."
    )
    include_raw_sample_rows: bool = Field(
        default=False,
        description="Whether to include full table sample rows in prompt.",
    )
    max_sample_values_per_col: int = Field(
        default=3, description="Maximum categorical sample values preserved per column."
    )
    retrieval_similarity_threshold: float = Field(
        default=0.35, description="Similarity threshold for BM25/Embedding matching."
    )

    # Advanced Prompting Configs (Phase 2)
    max_tokens: int = Field(
        default=16000, description="Stage output token generation limit."
    )
    compression_level: Literal["low", "medium", "high"] = Field(
        default="medium", description="Prompt section compression rigor."
    )
    sample_policy: Literal["strict_suppress", "smart_suppress", "keep_all"] = Field(
        default="smart_suppress", description="Sample suppression policy."
    )
    template_policy: Literal["minimal", "query_aware", "full"] = Field(
        default="query_aware", description="SQL template injection policy."
    )
    reasoning_depth: Literal["compact", "standard", "exhaustive"] = Field(
        default="standard", description="Reasoning prompt verbosity."
    )
    verbosity: Literal["low", "medium", "high"] = Field(
        default="medium", description="Overall prompt verbosity."
    )
    aggressive_trim: bool = Field(
        default=True,
        description="Whether to aggressively trim low-priority sections on token budget overflow.",
    )


LIGHTWEIGHT_CONFIG = PipelineModeConfig(
    mode="lightweight",
    max_tables_per_query=8,
    max_columns_per_table=12,
    schema_compression_level="aggressive",
    token_budget_limit=8000,
    include_raw_sample_rows=False,
    max_sample_values_per_col=1,
    retrieval_similarity_threshold=0.45,
    max_tokens=4096,
    compression_level="high",
    sample_policy="strict_suppress",
    template_policy="minimal",
    reasoning_depth="compact",
    verbosity="low",
    aggressive_trim=True,
)

BALANCED_CONFIG = PipelineModeConfig(
    mode="balanced",
    max_tables_per_query=250,
    max_columns_per_table=25,
    schema_compression_level="balanced",
    token_budget_limit=90000,
    include_raw_sample_rows=False,
    max_sample_values_per_col=3,
    retrieval_similarity_threshold=0.15,
    max_tokens=8192,
    compression_level="medium",
    sample_policy="smart_suppress",
    template_policy="query_aware",
    reasoning_depth="standard",
    verbosity="medium",
    aggressive_trim=True,
)

DEEP_REASONING_CONFIG = PipelineModeConfig(
    mode="deep_reasoning",
    max_tables_per_query=400,
    max_columns_per_table=50,
    schema_compression_level="verbose",
    token_budget_limit=120000,
    include_raw_sample_rows=True,
    max_sample_values_per_col=5,
    retrieval_similarity_threshold=0.15,
    max_tokens=16384,
    compression_level="low",
    sample_policy="keep_all",
    template_policy="full",
    reasoning_depth="exhaustive",
    verbosity="high",
    aggressive_trim=False,
)

CONFIG_MODES = {
    "lightweight": LIGHTWEIGHT_CONFIG,
    "balanced": BALANCED_CONFIG,
    "deep_reasoning": DEEP_REASONING_CONFIG,
}
