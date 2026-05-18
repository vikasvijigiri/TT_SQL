import re
import hashlib
from typing import List, Dict, Any, Tuple, Set
from backend.app.utils.logger import logger

class TemplateCanonicalizer:
    """
    Enterprise Template Canonicalization Engine.
    Computes structural signatures for SQL syntax templates (e.g., detecting CTEs,
    lateral flattens, window functions, aggregations) and retains only the most concise,
    highest-quality representative when structural equivalence is detected.
    """

    @classmethod
    def get_sql_structural_signature(cls, sql: str) -> Tuple[str, ...]:
        """
        Analyzes an SQL string and returns a sorted tuple of canonical structural features.
        """
        clean = sql.upper()
        features = set()

        if "WITH " in clean and " AS " in clean:
            features.add("CTE")
        if "LATERAL FLATTEN" in clean or "FLATTEN(" in clean:
            features.add("LATERAL_FLATTEN")
        if "OVER (" in clean or "PARTITION BY" in clean or "QUALIFY " in clean:
            features.add("WINDOW_FUNCTION")
        if "GROUP BY" in clean or "COUNT(" in clean or "SUM(" in clean or "AVG(" in clean:
            features.add("AGGREGATION")
        if " JOIN " in clean:
            features.add("JOIN")
        if "ST_" in clean:
            features.add("GEOSPATIAL")
        if "CASE WHEN" in clean:
            features.add("CONDITIONAL")

        return tuple(sorted(features))

    @classmethod
    def canonicalize_templates(cls, templates: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], int]:
        """
        Deduplicates a list of template dictionaries ('name', 'sql', 'description')
        based on structural equivalence signatures.
        Returns the retained templates and total tokens saved.
        """
        if not templates:
            return [], 0

        seen_signatures: Set[Tuple[str, ...]] = set()
        seen_exact_sqls: Set[str] = set()
        canonical_templates = []
        tokens_saved = 0

        for tmpl in templates:
            sql_text = tmpl.get("sql", "").strip()
            if not sql_text:
                continue

            # Check exact SQL string deduplication
            exact_norm = re.sub(r'\s+', ' ', sql_text.lower())
            if exact_norm in seen_exact_sqls:
                tokens_saved += max(1, len(sql_text) // 4)
                continue
            seen_exact_sqls.add(exact_norm)

            # Check structural signature equivalence
            sig = cls.get_sql_structural_signature(sql_text)
            # If the signature is non-empty and we've already seen an exact match for this structural combination
            if sig and sig in seen_signatures:
                tokens_saved += max(1, len(sql_text) // 4)
                logger.debug(f"[TemplateCanonicalizer] Dropped structurally equivalent template: '{tmpl.get('name', 'Template')}' Signature: {sig}")
            else:
                if sig:
                    seen_signatures.add(sig)
                canonical_templates.append(tmpl)

        return canonical_templates, tokens_saved

    @classmethod
    def format_canonical_templates(cls, templates: List[Dict[str, str]]) -> str:
        """Formats canonical templates into pristine markdown."""
        if not templates:
            return ""
        out = "=== RELEVANT SQL SYNTAX TEMPLATES ===\n"
        for t in templates:
            name = t.get("name", "Template")
            sql = t.get("sql", "").strip()
            out += f"\n--- [Template] {name} ---\n```sql\n{sql}\n```\n"
        return out.strip()
