from pydantic import BaseModel
from core.reasoning.confidence_estimator import ConfidenceMetrics
from core.retrieval.capability_detector import QueryCapabilityProfile
from core.utils.logger import logger


class AdaptiveCompressionPolicy(BaseModel):
    max_sample_values_per_col: int
    include_raw_sample_rows: bool
    max_schema_description_len: int
    preserve_templates: bool
    preserve_past_lessons: bool
    pruning_similarity_threshold: float


class AdaptiveCompressionEngine:
    """
    Enterprise Adaptive Compression Engine.
    Dynamically modulates schema, sample, and template compression rates based on
    query complexity, retrieval confidence, and budget pressure.
    """

    @classmethod
    def get_policy(
        cls,
        query: str,
        confidence: ConfidenceMetrics,
        profile: QueryCapabilityProfile,
        budget_pressure_ratio: float = 0.5,
    ) -> AdaptiveCompressionPolicy:
        # Determine query complexity
        is_complex = (
            profile.requires_windows
            or profile.requires_variants
            or profile.requires_joins
            or (len(query.split()) > 20)
        )
        is_ambiguous = confidence.is_low_confidence

        if is_ambiguous and budget_pressure_ratio < 0.5:
            # Preserve more guidance and examples when ambiguous or complex without extreme budget pressure
            policy = AdaptiveCompressionPolicy(
                max_sample_values_per_col=5,
                include_raw_sample_rows=True,
                max_schema_description_len=150,
                preserve_templates=True,
                preserve_past_lessons=True,
                pruning_similarity_threshold=0.85,
            )
            logger.info(
                "[AdaptiveCompressionEngine] Selected CONSERVATIVE compression policy (preserving guidance)."
            )
        elif not is_complex and confidence.composite_confidence > 0.85:
            # Simple query + high confidence -> aggressive compression
            policy = AdaptiveCompressionPolicy(
                max_sample_values_per_col=2,
                include_raw_sample_rows=False,
                max_schema_description_len=60,
                preserve_templates=False,
                preserve_past_lessons=False,
                pruning_similarity_threshold=0.75,
            )
            logger.info(
                "[AdaptiveCompressionEngine] Selected AGGRESSIVE compression policy (high confidence/simple query)."
            )
        else:
            # Balanced
            policy = AdaptiveCompressionPolicy(
                max_sample_values_per_col=3,
                include_raw_sample_rows=True,
                max_schema_description_len=100,
                preserve_templates=True,
                preserve_past_lessons=True,
                pruning_similarity_threshold=0.80,
            )
            logger.info(
                "[AdaptiveCompressionEngine] Selected BALANCED compression policy."
            )

        return policy
