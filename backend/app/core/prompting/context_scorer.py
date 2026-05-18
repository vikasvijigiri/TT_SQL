import re
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

class ContextQualityScore(BaseModel):
    is_acceptable: bool
    total_score: float
    relevance_density: float
    redundancy_ratio: float
    schema_noise_ratio: float
    rejection_reason: Optional[str] = None

class ContextQualityScorer:
    """
    Enterprise context quality auditing engine. Evaluates assembled prompt sections
    for relevance density, schema noise, and instruction redundancy before LLM invocation.
    """
    def __init__(self, min_acceptable_score: float = 0.35):
        self.min_acceptable_score = min_acceptable_score

    def evaluate_prompt(self, query: str, prompt_text: str, total_candidate_columns: int, relevant_columns_count: int) -> ContextQualityScore:
        q_tokens = set(re.findall(r'\w+', query.lower()))
        p_tokens = re.findall(r'\w+', prompt_text.lower())
        
        # 1. Relevance density (query tokens presence frequency in prompt)
        matches = sum(1 for t in p_tokens if t in q_tokens)
        relevance_density = min(1.0, (matches / max(1, len(p_tokens))) * 10.0)

        # 2. Redundancy ratio (unique tokens / total tokens)
        unique_tokens = set(p_tokens)
        redundancy_ratio = 1.0 - (len(unique_tokens) / max(1, len(p_tokens)))

        # 3. Schema noise ratio
        schema_noise_ratio = 1.0 - (relevant_columns_count / max(1, total_candidate_columns))

        # Composite score
        # Higher density is good, lower redundancy and noise is good
        score = (relevance_density * 0.5) + ((1.0 - redundancy_ratio) * 0.25) + ((1.0 - schema_noise_ratio) * 0.25)
        score = round(min(1.0, max(0.0, score)), 3)

        is_acc = score >= self.min_acceptable_score or relevant_columns_count > 0
        reason = f"Prompt quality score {score} below minimum threshold {self.min_acceptable_score}." if not is_acc else None

        return ContextQualityScore(
            is_acceptable=is_acc,
            total_score=score,
            relevance_density=round(relevance_density, 3),
            redundancy_ratio=round(redundancy_ratio, 3),
            schema_noise_ratio=round(schema_noise_ratio, 3),
            rejection_reason=reason
        )
