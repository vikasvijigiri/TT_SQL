from typing import List


def get_identifier_rules() -> List[str]:
    return [
        "Double-quote every table and column using exact SCHEMA casing. Unquoted identifiers fold to UPPERCASE and fail silently.",
        "Every identifier must exist verbatim in SCHEMA. No assumed, abbreviated, or pluralised names.",
        "Table function outputs (VALUE, INDEX, PATH, KEY, SEQ) are UPPERCASE. Never quote them.",
        "Never reference a SELECT-level alias in WHERE or HAVING.",
        "Prefer CTEs over nested subqueries. Each CTE maps to one logical step. Name CTEs in snake_case reflecting logical purpose.",
        "NEVER prefix table names with logical database names from the description (e.g., do NOT write 'businessinfo_database.business' or 'user_database.review'). The tables are exposed directly in the default schema. Only use the table names exactly as shown in the schema (e.g., \"business\", \"review\").",
    ]
