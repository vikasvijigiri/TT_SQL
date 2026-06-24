import hashlib
import re
from typing import List, Dict, Tuple
from core.utils.logger import logger


class DeduplicationTelemetry(dict):
    def __init__(
        self, raw_count: int = 0, dedup_count: int = 0, token_savings: int = 0
    ):
        super().__init__(
            raw_count=raw_count, dedup_count=dedup_count, token_savings=token_savings
        )


class RuleDeduplicator:
    """
    Enterprise Rule Deduplication Engine.
    Eliminates redundant dialect rules, repetitive past lessons, or overlapping SQL templates
    using text normalization and semantic hashing. Preserves highest-priority rules.
    """

    @staticmethod
    def normalize_rule(text: str) -> str:
        """Strips whitespace, punctuation, and casing to create a normalized matching string."""
        # Lowercase and remove punctuation, extra spaces, and bullet markers
        clean = re.sub(r"[^\w\s]", "", text.lower())
        return " ".join(clean.split())

    @staticmethod
    def semantic_hash(normalized_text: str) -> str:
        """Computes a sha256 hash of the normalized rule text."""
        return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    def deduplicate_rules(
        self, rules: List[str], priorities: List[int] | None = None
    ) -> Tuple[List[str], DeduplicationTelemetry]:
        """
        Deduplicates a list of rule strings. If priorities are provided (higher int = higher priority),
        keeps the highest priority version of duplicate rules.
        """
        if not rules:
            return [], DeduplicationTelemetry()

        raw_count = len(rules)
        raw_tokens = sum(max(1, len(r) // 4) for r in rules)

        # Default priority to index order if not provided
        if not priorities or len(priorities) != len(rules):
            priorities = [1] * len(rules)

        seen_hashes = {}
        kept_rules = []

        # Sort by priority descending so we encounter the highest priority items first
        paired = sorted(
            zip(rules, priorities, range(len(rules)), strict=False), key=lambda x: (-x[1], x[2])
        )

        for rule, _prio, orig_idx in paired:
            norm = self.normalize_rule(rule)
            if len(norm) < 5:  # Ignore empty or trivial lines
                continue
            shash = self.semantic_hash(norm)

            if shash not in seen_hashes:
                seen_hashes[shash] = (rule, orig_idx)

        # Sort back to original inclusion order for coherent reading flow
        sorted_kept = sorted(seen_hashes.values(), key=lambda x: x[1])
        kept_rules = [item[0] for item in sorted_kept]

        dedup_count = len(kept_rules)
        kept_tokens = sum(max(1, len(r) // 4) for r in kept_rules)
        savings = max(0, raw_tokens - kept_tokens)

        telemetry = DeduplicationTelemetry(
            raw_count=raw_count, dedup_count=dedup_count, token_savings=savings
        )
        if savings > 0:
            logger.debug(
                f"[RuleDeduplicator] Deduplicated {raw_count} -> {dedup_count} rules (~{savings} tokens saved)."
            )

        return kept_rules, telemetry

    def deduplicate_templates(
        self, templates: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], DeduplicationTelemetry]:
        """
        Deduplicates SQL template structures (dicts containing 'name', 'sql', 'description').
        Matches on normalized SQL structure.
        """
        if not templates:
            return [], DeduplicationTelemetry()

        raw_count = len(templates)
        raw_tokens = sum(max(1, len(t.get("sql", "")) // 4) for t in templates)

        seen_sql = set()
        kept_templates = []

        for tmpl in templates:
            sql_text = tmpl.get("sql", "")
            norm = re.sub(r"\s+", " ", sql_text.strip().lower())
            if norm not in seen_sql and norm:
                seen_sql.add(norm)
                kept_templates.append(tmpl)

        dedup_count = len(kept_templates)
        kept_tokens = sum(max(1, len(t.get("sql", "")) // 4) for t in kept_templates)
        savings = max(0, raw_tokens - kept_tokens)

        telemetry = DeduplicationTelemetry(
            raw_count=raw_count, dedup_count=dedup_count, token_savings=savings
        )
        if savings > 0:
            logger.debug(
                f"[RuleDeduplicator] Deduplicated {raw_count} -> {dedup_count} templates (~{savings} tokens saved)."
            )

        return kept_templates, telemetry
