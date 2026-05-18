from typing import List

def get_join_rules() -> List[str]:
    return [
        "INNER: intersection only. LEFT: preserve all left rows. Avoid RIGHT JOIN — rewrite as LEFT. CROSS: cartesian — only when explicitly required. Never implicit joins.",
        "Every JOIN requires ON with fully qualified TABLE.COLUMN on both sides. Never use USING or unqualified column names.",
        "Check JOIN keys for NULLs. Use EQUAL_NULL(a, b) for NULL-safe equality. Add IS NOT NULL filter on join key if NULLs inflate results.",
        "Row multiplication occurs when both join sides are non-unique on the join key. Deduplicate the non-unique side with ROW_NUMBER() before joining."
    ]
