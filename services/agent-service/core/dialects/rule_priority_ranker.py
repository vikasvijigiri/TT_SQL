from typing import List, Tuple
from agent.services.logger import logger


class RulePriorityRanker:
    """
    Enterprise Rule Priority Ranker.
    Classifies dialect rules into CRITICAL, MEDIUM, and LOW tiers.
    When token pressure is high, lower priority rules are trimmed first.
    """

    CRITICAL_KWS = (
        "double-quote",
        "identifier",
        "schema casing",
        "variant",
        ":",
        "lateral flatten",
        "group by",
        "inner",
        "left",
        "on",
        "critical",
        "regexp_extract",
        "regex",
        "json",
        "cast",
        "null",
        "strptime",
        "try_cast",
        # DuckDB attached-database qualifiers - must never be trimmed
        "db_alias",
        "attached",
        "qualify",
        "duckdb only",
        "always qualify",
    )
    LOW_KWS = (
        "srid",
        "st_geographyfromwkb",
        "st_geographyfromwkt",
        "approx_count_distinct",
        "hll",
    )

    @classmethod
    def rank_rules(cls, rules: List[str]) -> List[Tuple[str, str]]:
        """
        Returns a list of tuples (rule_text, priority_tier).
        Tiers: 'CRITICAL', 'MEDIUM', 'LOW'.
        """
        ranked = []
        for r in rules:
            r_lower = r.lower()
            if any(kw in r_lower for kw in cls.CRITICAL_KWS):
                tier = "CRITICAL"
            elif any(kw in r_lower for kw in cls.LOW_KWS):
                tier = "LOW"
            else:
                tier = "MEDIUM"
            ranked.append((r, tier))
        return ranked

    @classmethod
    def trim_rules_by_priority(
        cls, ranked_rules: List[Tuple[str, str]], max_rules: int = 20
    ) -> List[str]:
        if len(ranked_rules) <= max_rules:
            return [r[0] for r in ranked_rules]

        # Order by CRITICAL -> MEDIUM -> LOW
        critical = [r[0] for r in ranked_rules if r[1] == "CRITICAL"]
        medium = [r[0] for r in ranked_rules if r[1] == "MEDIUM"]
        low = [r[0] for r in ranked_rules if r[1] == "LOW"]

        retained = critical[:max_rules]
        if len(retained) < max_rules:
            retained += medium[: max_rules - len(retained)]
        if len(retained) < max_rules:
            retained += low[: max_rules - len(retained)]

        logger.warning(
            f"[RulePriorityRanker] Trimmed rules from {len(ranked_rules)} -> {len(retained)} based on priority tiers."
        )
        return retained
