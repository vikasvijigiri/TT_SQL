import numpy as np
from rapidfuzz import fuzz
from typing import Any, List, Union

def normalize(text):
    return str(text).lower().replace("_", " ").strip()

def value_score(value, samples):
    if not value or not samples:
        return 0.0

    values = value if isinstance(value, list) else [value]
    values = [str(v).lower().strip() for v in values]

    total = 0

    for v in values:
        best = 0

        for s in samples:
            s = str(s).lower()

            # exact match (strongest)
            if v == s:
                best = 1.0
                break

            # substring match
            if v in s:
                best = max(best, 0.9)

            # fuzzy match
            score = fuzz.partial_ratio(v, s) / 100
            best = max(best, score * 0.75)

        total += best

    return total / len(values)

def combined_score(term, value, col, term_vec, col_vec, samples):
    """
    STRICT VALUE-DOMINANT SCORING (Step 3)
    """
    from rapidfuzz import fuzz
    import numpy as np

    def cosine(a, b):
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    semantic = cosine(term_vec, col_vec)
    fuzzy = fuzz.token_sort_ratio(term, col) / 100
    val = value_score(value, samples)

    # Step 5: KILL INVALID COLUMNS
    if val == 0:
        return -1.0, semantic, fuzzy, 0.0

    # Step 3: STRICT VALUE DOMINANCE
    score = (
        0.05 * semantic +
        0.05 * fuzzy +
        0.9 * val
    )

    # Step 4: HARD OVERRIDE (VERY IMPORTANT)
    if val >= 0.95:
        score += 0.5

    return score, semantic, fuzzy, val
