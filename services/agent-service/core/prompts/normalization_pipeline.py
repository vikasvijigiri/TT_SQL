import re


class PromptNormalizationPipeline:
    """
    Enterprise Prompt Normalization Engine.
    Standardizes whitespace, bullet formats, rule prefixes, and redundant section headers
    to maximize reasoning density and prevent attention fragmentation.
    """

    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        """Collapses excessive newlines and trims trailing whitespace per line."""
        if not text:
            return ""
        # Remove trailing whitespace per line
        lines = [line.rstrip() for line in text.splitlines()]
        # Rejoin and collapse 3+ consecutive newlines into exactly 2
        collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
        return collapsed.strip()

    @classmethod
    def normalize_bullets(cls, text: str) -> str:
        """Standardizes various bullet styles (*, -, ', 1.) to uniform markdown bullet '- '."""
        if not text:
            return ""
        # Match lines starting with optional whitespace, then *, -, or ' followed by spaces
        normalized = re.sub(r"^(\s*)[\*\']\s+", r"\1- ", text, flags=re.MULTILINE)
        return normalized

    @classmethod
    def normalize_prefixes(cls, text: str) -> str:
        """Removes redundant descriptive tags like [Rule], [Directive], or category headers."""
        if not text:
            return ""
        # Remove tags like [Rule], [Directive], [Template], etc.
        clean = re.sub(
            r"\[(?:Rule|Directive|Template|Join Directives|Aggregation Directives|Null & Division Directives|Variant & JSON Directives|Geospatial Directives|Dialect Directives)\]:?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Clean up any leftover double spaces after prefix removal
        clean = re.sub(r" -  ", " - ", clean)
        return clean.strip()

    @classmethod
    def normalize_headers(cls, text: str) -> str:
        """Consolidates redundant section headers into a single clean title."""
        if not text:
            return ""
        # Detect and consolidate repeated dialect rule headers
        pattern_rules_header = re.compile(
            r"(?:===\s*SNOWFLAKE\s*DIALECT\s*RULES\s*===|QUERY-AWARE\s*DIALECT\s*RULES\s*FOR\s*SNOWFLAKE:?)[\s\n]*(?:===\s*SNOWFLAKE\s*DIALECT\s*RULES\s*===|QUERY-AWARE\s*DIALECT\s*RULES\s*FOR\s*SNOWFLAKE:?)?",
            re.IGNORECASE,
        )
        text = pattern_rules_header.sub("=== SNOWFLAKE DIALECT RULES ===", text)
        return text

    @classmethod
    def normalize(cls, text: str) -> str:
        """Executes the full prompt normalization pipeline."""
        if not text:
            return ""
        text = cls.normalize_bullets(text)
        text = cls.normalize_prefixes(text)
        text = cls.normalize_headers(text)
        text = cls.normalize_whitespace(text)
        return text
