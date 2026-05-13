from rapidfuzz import fuzz
import numpy as np
from typing import Any, List, Union, Optional
from src.utils.logger import logger
from src.core.config import get_settings

settings = get_settings()

# Thresholds loaded from settings
MIN_VALUE_SCORE = settings.GROUNDING_MIN_VALUE_SCORE
STRONG_VALUE_SCORE = settings.GROUNDING_STRONG_VALUE_SCORE
MIN_SEMANTIC_SCORE = settings.GROUNDING_MIN_SEMANTIC_SCORE

def normalize(text: Any) -> str:
    """Normalizes text for comparison."""
    if text is None:
        return ""
    return str(text).lower().strip()

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculates cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def fuzzy_match(a: Any, b: Any) -> float:
    """Calculates fuzzy match score between 0 and 1."""
    return fuzz.ratio(normalize(a), normalize(b)) / 100.0

def compute_value_score(value: Any, samples: List[Any]) -> float:
    """
    Computes value match score. 
    Returns 1.0 for exact match, 0.9 for substring, and fuzzy match * 0.7 otherwise.
    """
    if not value or not samples:
        return 0.0

    values = value if isinstance(value, list) else [value]
    scores = []

    for v in values:
        v_norm = normalize(v)
        best = 0.0

        for s in samples:
            s_norm = normalize(s)

            if v_norm == s_norm:
                best = 1.0
                break

            if v_norm in s_norm:
                best = max(best, 0.9)

            f_score = fuzzy_match(v_norm, s_norm)
            best = max(best, f_score * 0.7)

        scores.append(best)

    return sum(scores) / len(scores) if scores else 0.0

def score_column(term: str, value: Any, column: str, samples: List[Any], term_vec: np.ndarray, col_vec: np.ndarray) -> Optional[dict]:
    """
    Main scoring function for a column.
    Enforces strict value-first grounding with threshold guards.
    """
    val_score = compute_value_score(value, samples)

    # HARD REJECTION: Accept only strong value matches
    if val_score < MIN_VALUE_SCORE:
        return None

    semantic_score = cosine_similarity(term_vec, col_vec)
    fuzzy_score = fuzzy_match(term, column)

    # SEMANTIC GUARD: Prevents random matches when value is not decisive
    if val_score < STRONG_VALUE_SCORE and semantic_score < MIN_SEMANTIC_SCORE:
        return None

    # VALUE-DOMINANT SCORE (85% value, 10% semantic, 5% fuzzy)
    score = (
        0.85 * val_score +
        0.1 * semantic_score +
        0.05 * fuzzy_score
    )

    # STRONG VALUE BOOST
    if val_score >= STRONG_VALUE_SCORE:
        score += 0.3

    logger.debug(f"Scoring: col={column}, val={val_score:.2f}, sem={semantic_score:.2f}, final={score:.2f}")

    return {
        "score": score,
        "value_score": val_score,
        "semantic_score": semantic_score,
        "fuzzy_score": fuzzy_score
    }
