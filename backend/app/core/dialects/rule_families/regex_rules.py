from typing import List

def get_regex_rules() -> List[str]:
    return [
        "Case-sensitive pattern: LIKE. Case-insensitive: ILIKE. Regex match: REGEXP_LIKE. Regex extract: REGEXP_SUBSTR. Regex replace: REGEXP_REPLACE. Never use SIMILAR TO."
    ]
