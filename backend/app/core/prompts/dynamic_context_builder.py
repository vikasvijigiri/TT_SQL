from typing import List, Dict, Any, Optional
from backend.app.models.schemas import SemanticContext
from backend.app.core.pipeline_config import PipelineModeConfig, BALANCED_CONFIG
from backend.app.core.schema.schema_compressor import SchemaCompressor
from backend.app.core.schema.sampling_policy import SchemaSamplingPolicy
from backend.app.core.dialects.rule_retriever import DialectRuleRetriever
from backend.app.core.retrieval.hierarchical_retriever import QueryIntentAnalysis

class DynamicContextBuilder:
    """
    Enterprise dynamic context builder. Coordinates schema compression,
    sampling policies, and query-aware dialect rules into clean, token-efficient
    context blocks for LLM prompt generation.
    """
    def __init__(self, config: PipelineModeConfig = BALANCED_CONFIG, dialect: str = "snowflake"):
        self.config = config
        self.compressor = SchemaCompressor(config)
        self.sampling = SchemaSamplingPolicy()
        self.rule_retriever = DialectRuleRetriever(dialect)

    def build_dynamic_schema(self, context: SemanticContext, relevant_tables: List[str] = None, table_columns: Dict[str, List[str]] = None, is_sf: bool = True) -> str:
        return self.compressor.compress_database_schema(
            context=context,
            is_sf=is_sf,
            relevant_tables=relevant_tables,
            table_columns=table_columns
        )

    def build_dialect_rules(self, intent: QueryIntentAnalysis) -> str:
        return self.rule_retriever.retrieve_relevant_rules(intent)
