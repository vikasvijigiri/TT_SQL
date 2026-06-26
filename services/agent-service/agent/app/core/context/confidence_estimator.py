from typing import Optional
from pydantic import BaseModel
from agent.app.models.schemas import SemanticContext
from agent.app.core.retrieval.hierarchical_retriever import QueryIntentAnalysis
from agent.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from agent.services.logger import logger


class ConfidenceMetrics(BaseModel):
    schema_confidence: float
    join_confidence: float
    semantic_mapping_confidence: float
    rule_confidence: float
    retrieval_confidence: float
    composite_confidence: float
    is_low_confidence: bool


class ConfidenceEstimator:
    """
    Enterprise Confidence Estimation Engine.
    Evaluates retrieval signals, schema complexity, and semantic mapping clarity
    to dynamically scale prompt guidance and safeguards.
    """

    LOW_CONFIDENCE_THRESHOLD = 0.65

    @classmethod
    def estimate(
        cls,
        query: str,
        context: Optional[SemanticContext] = None,
        intent: Optional[QueryIntentAnalysis] = None,
        profile: Optional[QueryCapabilityProfile] = None,
    ) -> ConfidenceMetrics:
        # 1. Schema Confidence
        # More tables/columns in context without clear narrowing lowers confidence
        num_tables = len(context.tables) if context and context.tables else 1
        num_cols = (
            sum(len(t.columns) for t in context.tables)
            if context and context.tables
            else 10
        )
        schema_conf = max(0.4, 1.0 - (num_tables * 0.05) - (num_cols * 0.005))

        # 2. Join Confidence
        # Queries requiring joins across many tables have lower join confidence
        if profile and profile.requires_joins:
            join_conf = max(0.5, 1.0 - (num_tables * 0.1))
        else:
            join_conf = 1.0

        # 3. Semantic Mapping Confidence
        # Queries with specific value-like terms or complex domain terms
        q_len = len(query.split())
        if intent and len(intent.target_entities) > 5:
            mapping_conf = 0.70
        else:
            mapping_conf = max(0.5, 1.0 - (q_len * 0.01))

        # 4. Rule & Retrieval Confidence
        rule_conf = 0.90 if profile and not profile.requires_variants else 0.75
        retrieval_conf = (
            0.85 if intent and intent.inferred_domain != "General Enterprise" else 0.70
        )

        # Composite weighting
        comp = (
            (schema_conf * 0.3)
            + (join_conf * 0.25)
            + (mapping_conf * 0.2)
            + (retrieval_conf * 0.15)
            + (rule_conf * 0.1)
        )
        comp = round(min(1.0, max(0.1, comp)), 2)

        is_low = comp < cls.LOW_CONFIDENCE_THRESHOLD

        metrics = ConfidenceMetrics(
            schema_confidence=round(schema_conf, 2),
            join_confidence=round(join_conf, 2),
            semantic_mapping_confidence=round(mapping_conf, 2),
            rule_confidence=round(rule_conf, 2),
            retrieval_confidence=round(retrieval_conf, 2),
            composite_confidence=comp,
            is_low_confidence=is_low,
        )

        logger.debug(
            f"[ConfidenceEstimator] Confidence estimated: {comp} (Low? {is_low})"
        )
        return metrics
