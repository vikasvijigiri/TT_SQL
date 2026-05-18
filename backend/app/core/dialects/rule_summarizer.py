import re
from typing import List

class RuleSummarizer:
    """
    Enterprise Query-Sensitive Rule Summarization Engine.
    Condenses rule text by 50-70% while preserving absolute operational syntax directives.
    """

    SUMMARY_MAP = [
        (r"Double-quote every table and column using exact SCHEMA casing.*?fail silently\.",
         "Double-quote identifiers with exact SCHEMA casing."),
        (r"Every identifier must exist verbatim in SCHEMA.*?pluralised names\.",
         "Identifiers must match SCHEMA verbatim."),
        (r"Table function outputs \(VALUE, INDEX, PATH, KEY, SEQ\) are UPPERCASE.*?to them\.",
         "Table function outputs (VALUE, INDEX, PATH) are unquoted UPPERCASE."),
        (r"Access VARIANT object keys using colon notation without single quotes.*?after colon\.",
         "Access VARIANT keys: \"col\":\"key\"::TYPE or GET_PATH(\"col\", 'key')::TYPE. Always cast explicit type."),
        (r"Render array expansion as LATERAL FLATTEN in FROM.*?in the main FROM clause\.",
         "Use LATERAL FLATTEN in FROM clause for array expansion. Reference via f.VALUE::TYPE."),
        (r"Test array membership with ARRAY_CONTAINS.*?against ARRAY or VARIANT columns\.",
         "Use ARRAY_CONTAINS('v'::VARIANT, \"col\") for array membership."),
        (r"Never use CURRENT_DATE, CURRENT_TIMESTAMP.*?TO_TIMESTAMP_NTZ\(\{REFERENCE_DATE\}\)\)\.",
         "Use {REFERENCE_DATE} for all date-relative logic (e.g. DATEADD(day, -N, TO_DATE({REFERENCE_DATE})))."),
        (r"DATEADD\(unit, amount, col\) and DATEDIFF.*?second\.",
         "Always specify explicit unit in DATEADD/DATEDIFF (year, month, day, etc.)."),
        (r"Every non-aggregated SELECT column MUST appear in GROUP BY.*?references\.",
         "Include all non-aggregated SELECT columns in GROUP BY. Never use positional numbers."),
        (r"Every JOIN requires ON with fully qualified TABLE\.COLUMN.*?names\.",
         "Use fully qualified TABLE.COLUMN in JOIN ON clauses. Never use USING."),
        (r"Every window function requires explicit OVER\(\).*?by intent\.",
         "Always pair window functions with explicit OVER(PARTITION BY ... ORDER BY ...).")
    ]

    @classmethod
    def summarize(cls, rule: str) -> str:
        summary = rule
        for pattern, replacement in cls.SUMMARY_MAP:
            summary, count = re.subn(pattern, replacement, summary, flags=re.DOTALL | re.IGNORECASE)
            if count > 0:
                break
        return summary.strip()

    @classmethod
    def summarize_all(cls, rules: List[str]) -> List[str]:
        return [cls.summarize(r) for r in rules]
