import re


class SystemPromptCompactor:
    """
    Enterprise System Prompt Compactor.
    Transforms verbose role-playing prose (~500 tokens) into strict operational
    constraints (150-250 tokens) enforcing universal SQL guarantees.
    """

    COMPACT_SYSTEM_TEMPLATE = """=== OPERATIONAL CONSTRAINTS ===
1. Generate exact {dialect} SQL. Output strictly valid JSON matching required response schema.
2. Prevent hallucinated identifiers: Every table and column must match provided SCHEMA verbatim. Double-quote all identifiers matching schema casing precisely.
3. Preserve aggregation grain: All non-aggregated SELECT columns must appear in GROUP BY.
4. Enforce dialect-safe casting: Use {cast_rule} for type coercion and keep casts consistent with the target database.
5. Prevent division-by-zero: Use NULLIF(denominator, 0).
6. Ensure syntax exactness: Semicolon termination, no unquoted reserved keywords."""

    @classmethod
    def compact(cls, raw_system_prompt: str, dialect: str = "SNOWFLAKE") -> str:
        # Check if already compacted
        if "=== OPERATIONAL CONSTRAINTS ===" in raw_system_prompt:
            return raw_system_prompt.strip()

        # If the system prompt is a custom-engineered specialized prompt,
        # we MUST preserve its rich operational rules, checklists, and guidelines
        # to ensure the respective agents function with high precision.
        custom_markers = [
            "Forensic Auditor",
            "schema linking engineer",
            "Result Validator",
            "Table Pruner",
            "Column Pruner",
            "OPERATIONAL DIRECTIVES:",
            "CRITICAL SAFEGUARDS",
            "CRITICAL MANDATORY RULE",
            "CRITICAL PRUNING GUARANTEES",
            "CRITICAL COLUMN SELECTION GUARANTEES",
            "alias existence verification",
            "Snowflake folds unquoted names to UPPERCASE",
        ]
        if (
            any(marker in raw_system_prompt for marker in custom_markers)
            or len(raw_system_prompt.strip()) > 300
        ):
            from core.utils.logger import logger

            logger.debug(
                "[SystemPromptCompactor] Preserving custom-engineered specialized system prompt."
            )
            return raw_system_prompt.strip()

        # Extract agent specific target schema or intent if present in raw
        agent_match = re.search(
            r"high-precision enterprise (\w+) agent", raw_system_prompt, re.IGNORECASE
        )
        agent = agent_match.group(1).upper() if agent_match else "SQL_GENERATOR"

        header = f"=== AGENT ROLE: {agent} ==="
        dialect_upper = dialect.upper()
        cast_rule = _DIALECT_CAST_RULE.get(dialect_upper, "CAST(expr AS TYPE)")
        body = cls.COMPACT_SYSTEM_TEMPLATE.format(
            dialect=dialect_upper, cast_rule=cast_rule
        )
        return f"{header}\n{body}"


# Canonical cast rule per dialect -- covers all DBMSes in DataAgentBench and Spider2.
# Key = dialect.upper(), value = human-readable rule injected into the system prompt.
_DIALECT_CAST_RULE: dict = {
    "SQLITE": "CAST(expr AS INTEGER|REAL|TEXT|BLOB)",
    "DUCKDB": "CAST(expr AS TYPE) or expr::TYPE",
    "POSTGRESQL": "double-colon casts (expr::TYPE)",
    "POSTGRES": "double-colon casts (expr::TYPE)",
    "REDSHIFT": "double-colon casts (expr::TYPE)",
    "MYSQL": "CAST(expr AS CHAR|SIGNED|DECIMAL|DATETIME)",
    "MSSQL": "CAST(expr AS TYPE) or CONVERT(TYPE, expr)",
    "SQLSERVER": "CAST(expr AS TYPE) or CONVERT(TYPE, expr)",
    "ORACLE": "TO_CHAR(expr) / TO_NUMBER(expr) / CAST(expr AS TYPE)",
    "BIGQUERY": "CAST(expr AS TYPE) or SAFE_CAST(expr AS TYPE)",
    "SNOWFLAKE": "double-colon casts (::TYPE) or TRY_CAST(expr AS TYPE)",
    "TRINO": "CAST(expr AS TYPE)",
    "PRESTO": "CAST(expr AS TYPE)",
    "MONGODB": "N/A -- use aggregation pipeline $convert operator",
    "SPARK": "CAST(expr AS TYPE) or expr::TYPE",
}
