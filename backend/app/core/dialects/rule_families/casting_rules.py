from typing import List

def get_casting_rules() -> List[str]:
    return [
        "Normalize all casts to double-colon notation: col::TYPE. Type aliases: VARCHAR/TEXT → STRING. INT/BIGINT → INTEGER. DOUBLE/DECIMAL → FLOAT. DATETIME → TIMESTAMP_NTZ. Never use ::VARCHAR.",
        "Use TRY_CAST(col AS TYPE) when a column may contain unconvertible values and NULL on failure is acceptable."
    ]
