class ReasoningDirectives:
    """
    Compact operational directives for specific SQL reasoning domains.
    Replaces verbose philosophical prose with direct, actionable instructions.
    """
    
    JOIN_SAFETY = """[JOIN DIRECTIVES]: 
- Verify foreign key to primary key relationships before joining.
- Avoid unmediated many-to-many joins. If joining a 1-to-many relationship, pre-aggregate the many side before joining to preserve fact table row grain."""

    AGGREGATION = """[AGGREGATION DIRECTIVES]:
- Match exactly the business grain requested by the user.
- Every non-aggregated column in SELECT MUST be explicitly listed in GROUP BY.
- When computing averages or percentages, verify the denominator correctly accounts for the target population."""

    NULL_HANDLING = """[NULL & DIVISION DIRECTIVES]:
- Wrap division denominators with NULLIF(denominator, 0) or use explicit CASE WHEN col != 0 to prevent division by zero errors.
- Explicitly handle NULLs in sums/counts using COALESCE(col, 0) where appropriate."""

    VARIANT_EXTRACTION = """[VARIANT & JSON DIRECTIVES]:
- When extracting keys from semi-structured VARIANT/JSON columns, use explicit colon extraction (col:"nested_key") or GET_PATH(col, 'key') and immediately cast to the target type (e.g., ::STRING, ::INTEGER, ::FLOAT).
- Do not quote table function outputs like VALUE, INDEX, KEY, PATH."""

    GEOSPATIAL = """[GEOSPATIAL DIRECTIVES]:
- When calculating areas, perimeters, distances, or intersections, use explicit ST_ spatial functions (e.g., ST_AREA(ST_GEOGRAPHYFROMWKT(col))).
- Do not filter on raw geography strings directly; use spatial bounding or containment predicates."""

    DIALECT_SAFETY = """[DIALECT DIRECTIVES]:
- In Snowflake, unquoted identifiers fold to UPPERCASE. Strictly double-quote all lowercase or mixed-case schema, table, and column names ("schema"."table"."column")."""

    @classmethod
    def get_all_directives(cls) -> str:
        return "\n\n".join([
            cls.JOIN_SAFETY, cls.AGGREGATION, cls.NULL_HANDLING,
            cls.VARIANT_EXTRACTION, cls.GEOSPATIAL, cls.DIALECT_SAFETY
        ])
