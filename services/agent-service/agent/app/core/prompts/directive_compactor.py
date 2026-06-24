from typing import Tuple
from agent.app.utils.logger import logger


class DirectiveCompactor:
    """
    Enterprise Directive Compaction Engine.
    Surgically condenses verbose reasoning directives by ~70% into actionable,
    high-density micro-instructions, preserving operational rigor while minimizing token overhead.
    """

    COMPACT_MAPPINGS = {
        "verify foreign key to primary key relationships": "Validate FK/PK joins.",
        "avoid unmediated many-to-many joins": "Pre-aggregate 1-to-many joins to preserve fact grain.",
        "match exactly the business grain": "Preserve requested grain.",
        "every non-aggregated column in select": "Include all SELECT non-aggregates in GROUP BY.",
        "when computing averages or percentages": "Verify AVG/PCT denominators.",
        "wrap division denominators with nullif": "Wrap division denominators with NULLIF(col, 0).",
        "explicitly handle nulls in sums/counts": "COALESCE NULLs in SUM/COUNT.",
        "when extracting keys from semi-structured variant": "Use col:key::type or GET_PATH() for VARIANT.",
        "do not quote table function outputs": "Do not quote VALUE, INDEX, KEY, PATH.",
        "when calculating areas, perimeters, distances": "Use ST_ functions for geospatial.",
        "do not filter on raw geography strings": "Use spatial containment predicates.",
        "unquoted identifiers fold": "Strictly double-quote mixed/lowercase identifiers.",
    }

    COMPACT_BLOCKS = {
        "JOIN_SAFETY": "- Validate FK/PK joins.\n- Pre-aggregate 1-to-many joins to preserve fact grain.",
        "AGGREGATION": "- Preserve requested grain.\n- Include all SELECT non-aggregates in GROUP BY.\n- Verify AVG/PCT denominators.",
        "NULL_HANDLING": "- Wrap division denominators with NULLIF(col, 0).\n- COALESCE NULLs in SUM/COUNT.",
        "VARIANT_EXTRACTION": "- Use col:key::type or GET_PATH() for VARIANT.\n- Do not quote VALUE, INDEX, KEY, PATH.",
        "GEOSPATIAL": "- Use ST_ functions for geospatial.\n- Use spatial containment predicates.",
        "DIALECT_SAFETY": "- Strictly double-quote mixed/lowercase identifiers.",
    }

    @classmethod
    def get_compact_all(cls) -> str:
        """Returns all reasoning directives in their ultra-compact, 70%-reduced form."""
        compact_text = "=== REASONING DIRECTIVES ===\n" + "\n".join(
            cls.COMPACT_BLOCKS.values()
        )
        return compact_text.strip()

    @classmethod
    def compact_directives(cls, raw_directives_text: str) -> Tuple[str, int]:
        """
        Scans raw directive text and replaces verbose clauses with compact equivalents.
        Returns the compacted text and total tokens saved.
        """
        if not raw_directives_text:
            return "", 0

        raw_tokens = max(1, len(raw_directives_text) // 4)

        # If it's the standard ReasoningDirectives output, return the pristine block
        if (
            "JOIN DIRECTIVES" in raw_directives_text
            or "AGGREGATION DIRECTIVES" in raw_directives_text
        ):
            compact_text = cls.get_compact_all()
            comp_tokens = max(1, len(compact_text) // 4)
            savings = max(0, raw_tokens - comp_tokens)
            logger.debug(
                f"[DirectiveCompactor] Compacted directives (~{savings} tokens saved, ~{round(savings / raw_tokens * 100, 1)}% reduction)."
            )
            return compact_text, savings

        # Fallback line-by-line replacement
        compacted = raw_directives_text.lower()
        for verbose, compact in cls.COMPACT_MAPPINGS.items():
            if verbose in compacted:
                # Replace the entire line containing verbose phrase with compact
                lines = raw_directives_text.splitlines()
                clean_lines = []
                for line in lines:
                    if verbose in line.lower():
                        clean_lines.append(f"- {compact}")
                    else:
                        clean_lines.append(line)
                raw_directives_text = "\n".join(clean_lines)

        comp_tokens = max(1, len(raw_directives_text) // 4)
        savings = max(0, raw_tokens - comp_tokens)
        return raw_directives_text.strip(), savings
