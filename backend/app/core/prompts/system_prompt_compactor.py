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
4. Enforce strict type casting: Always apply double-colon casts (::TYPE) for variant access, array indexing, and temporal functions.
5. Prevent division-by-zero: Use NULLIF(denominator, 0).
6. Ensure syntax exactness: Semicolon termination, no unquoted reserved keywords."""

    @classmethod
    def compact(cls, raw_system_prompt: str, dialect: str = "SNOWFLAKE") -> str:
        # Check if already compacted
        if "=== OPERATIONAL CONSTRAINTS ===" in raw_system_prompt:
            return raw_system_prompt.strip()

        # Extract agent specific target schema or intent if present in raw
        agent_match = re.search(r'high-precision enterprise (\w+) agent', raw_system_prompt, re.IGNORECASE)
        agent = agent_match.group(1).upper() if agent_match else "SQL_GENERATOR"

        header = f"=== AGENT ROLE: {agent} ==="
        body = cls.COMPACT_SYSTEM_TEMPLATE.format(dialect=dialect.upper())
        return f"{header}\n{body}"
