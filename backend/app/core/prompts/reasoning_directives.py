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

    _DIALECT_SAFETY_SNOWFLAKE = """[DIALECT DIRECTIVES]:
- In Snowflake, unquoted identifiers fold to UPPERCASE. Strictly double-quote all lowercase or mixed-case schema, table, and column names ("schema"."table"."column")."""

    _DIALECT_SAFETY_POSTGRES = """[DIALECT DIRECTIVES]:
- In PostgreSQL, unquoted identifiers fold to lowercase. If a table or column name contains uppercase letters, wrap it in double quotes to preserve the original case."""

    _DIALECT_SAFETY_GENERIC = """[DIALECT DIRECTIVES]:
- Quote identifier names according to the dialect's casing rules. Use double quotes around any table or column names that are not all-lowercase (DuckDB, SQLite) or all-uppercase (Snowflake) to prevent silent name-resolution failures."""

    SQLITE_TIME_SERIES = """[SQLITE TIME-SERIES DIRECTIVES]:
- Declare recursive queries with a single WITH RECURSIVE clause at the top of the statement.
- Pre-aggregate to the natural grain before recursion; compute the row ordering key explicitly with ROW_NUMBER() when needed.
- Use CAST(expr AS INTEGER/REAL/TEXT) in SQLite and avoid PostgreSQL-style ::TYPE casts."""

    @classmethod
    def get_dialect_safety(cls, dialect: str) -> str:
        d = dialect.lower()
        if d == "snowflake":
            return cls._DIALECT_SAFETY_SNOWFLAKE
        if d in ("postgres", "postgresql", "redshift"):
            return cls._DIALECT_SAFETY_POSTGRES
        return cls._DIALECT_SAFETY_GENERIC

    @classmethod
    def get_all_directives(cls, dialect: str = "snowflake", include_sqlite_time_series: bool = False) -> str:
        directives = [
            cls.JOIN_SAFETY, cls.AGGREGATION, cls.NULL_HANDLING,
            cls.VARIANT_EXTRACTION, cls.GEOSPATIAL, cls.get_dialect_safety(dialect)
        ]
        if dialect.lower() == "sqlite" and include_sqlite_time_series:
            directives.append(cls.SQLITE_TIME_SERIES)
        return "\n\n".join(directives)
