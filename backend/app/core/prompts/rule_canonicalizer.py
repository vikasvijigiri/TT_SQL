from typing import List, Dict, Tuple, Set
from backend.app.core.prompts.global_deduplicator import GlobalPromptDeduplicator
from backend.app.utils.logger import logger

class RuleCanonicalizer:
    """
    Enterprise Rule Canonicalization Engine.
    Standardizes dialect rules, past lessons, and directives into canonical, authoritative
    phrasings to prevent redundant rule injection across pipeline stages.
    """

    CANONICAL_REGISTRY = {
        "double quote identifiers": "Strictly double-quote all lowercase or mixed-case identifiers (\"schema\".\"table\".\"column\").",
        "quote identifiers": "Strictly double-quote all lowercase or mixed-case identifiers (\"schema\".\"table\".\"column\").",
        "uppercase unquoted identifiers": "Strictly double-quote all lowercase or mixed-case identifiers (\"schema\".\"table\".\"column\").",
        "colon extraction": "Use explicit colon extraction (col:\"nested_key\"::type) or GET_PATH(col, 'key')::type for VARIANT columns.",
        "variant json extraction": "Use explicit colon extraction (col:\"nested_key\"::type) or GET_PATH(col, 'key')::type for VARIANT columns.",
        "parse json": "Use explicit colon extraction (col:\"nested_key\"::type) or GET_PATH(col, 'key')::type for VARIANT columns.",
        "division by zero": "Wrap division denominators with NULLIF(denominator, 0) to prevent division by zero errors.",
        "nullif denominator": "Wrap division denominators with NULLIF(denominator, 0) to prevent division by zero errors.",
        "coalesce sums counts": "Explicitly handle NULLs in aggregations using COALESCE(col, 0).",
        "verify foreign key primary key": "Validate FK/PK relationships before joining to prevent row duplication.",
        "avoid unmediated many to many": "Pre-aggregate the many side in 1-to-many joins to preserve fact table grain.",
        "every non aggregated column": "Every non-aggregated column in SELECT MUST be explicitly listed in GROUP BY.",
        "do not quote table function": "Do not quote table function outputs like VALUE, INDEX, KEY, PATH.",
        "geospatial calculating areas perimeters": "Use explicit ST_ spatial functions (e.g., ST_AREA(ST_GEOGRAPHYFROMWKT(col))).",
        "spatial bounding containment predicates": "Do not filter raw geography strings; use spatial containment predicates."
    }

    @classmethod
    def get_canonical_rule(cls, raw_rule: str) -> str:
        """
        Maps a raw rule string to its canonical registry entry if a strong semantic match is found.
        Otherwise returns the clean raw rule.
        """
        key = GlobalPromptDeduplicator.get_core_semantic_key(raw_rule)
        for reg_key, canonical_text in cls.CANONICAL_REGISTRY.items():
            if GlobalPromptDeduplicator.compute_jaccard_similarity(key, reg_key) >= 0.75 or reg_key in key:
                return canonical_text
        return raw_rule.strip()

    @classmethod
    def canonicalize_and_deduplicate(cls, raw_rules: List[str], global_seen_rules: Set[str] = None) -> Tuple[List[str], int]:
        """
        Executes the canonicalization pipeline:
        raw_rules -> normalize -> canonicalize -> deduplicate -> inject once.
        Returns the clean rule list and token savings.
        """
        if global_seen_rules is None:
            global_seen_rules = set()

        canonical_list = []
        tokens_saved = 0

        for r in raw_rules:
            r_str = r.strip()
            if not r_str or len(r_str) < 5:
                continue
                
            canonical = cls.get_canonical_rule(r_str)
            key = GlobalPromptDeduplicator.get_core_semantic_key(canonical)
            
            is_dup = False
            if key in global_seen_rules or canonical in global_seen_rules:
                is_dup = True
            else:
                for seen in global_seen_rules:
                    if GlobalPromptDeduplicator.compute_jaccard_similarity(key, GlobalPromptDeduplicator.get_core_semantic_key(seen)) >= 0.85:
                        is_dup = True
                        break

            if is_dup:
                tokens_saved += max(1, len(r_str) // 4)
                logger.debug(f"[RuleCanonicalizer] Suppressed duplicate rule: '{r_str[:50]}...'")
            else:
                global_seen_rules.add(key)
                global_seen_rules.add(canonical)
                canonical_list.append(canonical)

        return canonical_list, tokens_saved
