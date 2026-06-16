from typing import List, Any, Tuple
from pydantic import BaseModel
from agent.app.utils.logger import logger


class ContextItemScore(BaseModel):
    item_name: str
    item_type: str
    usefulness_score: float
    necessity_score: float
    hallucination_prevention_score: float
    composite_value: float


class ContextValueRanker:
    """
    Enterprise Context Value Scoring & Ranking Engine.
    Evaluates prompt sections and context items on usefulness, syntax necessity,
    and hallucination prevention value, trimming lowest-value items first under token pressure.
    Supports both PromptSection and PromptNode objects.
    """

    DEFAULT_SCORES = {
        "dynamic_schema": (0.95, 1.0, 1.0),  # Primary grounding
        "dialect_rules": (0.90, 0.95, 0.95),  # Syntax exactness
        "reasoning_directives": (0.85, 0.90, 0.90),  # Structural guidance
        "syntax_templates": (0.80, 0.70, 0.75),  # Helpful patterns
        "past_lessons": (0.75, 0.65, 0.80),  # Historical corrections
        "error_history": (0.95, 0.90, 0.95),  # Immediate correction
    }

    @classmethod
    def score_section(cls, section: Any) -> ContextItemScore:
        use, nec, hal = cls.DEFAULT_SCORES.get(section.name, (0.70, 0.60, 0.70))

        # Adjust based on section droppability
        if not getattr(section, "droppable", True):
            nec = 1.0
            hal = max(hal, 0.95)

        comp = round((use * 0.3) + (nec * 0.35) + (hal * 0.35), 3)
        item_type = getattr(section, "section_type", "general")

        return ContextItemScore(
            item_name=section.name,
            item_type=item_type,
            usefulness_score=use,
            necessity_score=nec,
            hallucination_prevention_score=hal,
            composite_value=comp,
        )

    @classmethod
    def rank_and_trim(
        cls, sections: List[Any], max_budget: int, token_estimator
    ) -> Tuple[List[Any], List[str]]:
        scored = []
        for sec in sections:
            score = cls.score_section(sec)
            sec.semantic_value = score.composite_value
            scored.append((sec, score.composite_value))

        # Sort by droppability (False first), then composite value descending
        ranked = sorted(
            scored,
            key=lambda x: (0 if not getattr(x[0], "droppable", True) else 1, -x[1]),
        )

        retained = []
        dropped = []
        current_tokens = 0

        for sec, val in ranked:
            content_str = (
                getattr(sec, "content", "")
                if isinstance(getattr(sec, "content", ""), str)
                else str(getattr(sec, "content", ""))
            )
            est_tokens = token_estimator(content_str)
            if not getattr(sec, "droppable", True) or current_tokens + est_tokens <= max_budget:
                retained.append(sec)
                current_tokens += est_tokens
            else:
                dropped.append(sec.name)
                logger.warning(
                    f"[ContextValueRanker] Trimmed section '{sec.name}' (Value: {val}) to stay within {max_budget} budget."
                )

        # Reconstruct in original structural order
        original_order = {s.name: idx for idx, s in enumerate(sections)}
        retained_ordered = sorted(retained, key=lambda x: original_order[x.name])

        return retained_ordered, dropped
