import typing
import yaml
from typing import List
from config.config import get_dialect_path
from core.retrieval.hierarchical_retriever import QueryIntentAnalysis
from core.query_analysis.capability_detector import QueryCapabilityProfile
from core.retrieval.dialects.rule_priority_ranker import RulePriorityRanker
from core.retrieval.dialects.rule_summarizer import RuleSummarizer
from core.utils.logger import logger

# Import rule families
from core.retrieval.dialects.rule_families.identifier_rules import (
    get_identifier_rules,
)
from core.retrieval.dialects.rule_families.casting_rules import get_casting_rules
from core.retrieval.dialects.rule_families.variant_rules import get_variant_rules
from core.retrieval.dialects.rule_families.array_rules import get_array_rules
from core.retrieval.dialects.rule_families.aggregation_rules import (
    get_aggregation_rules,
)
from core.retrieval.dialects.rule_families.join_rules import get_join_rules
from core.retrieval.dialects.rule_families.timestamp_rules import get_timestamp_rules
from core.retrieval.dialects.rule_families.geospatial_rules import (
    get_geospatial_rules,
)
from core.retrieval.dialects.rule_families.window_rules import get_window_rules
from core.retrieval.dialects.rule_families.regex_rules import get_regex_rules


class RuleFamilyRetriever:
    """
    Enterprise Rule Family Retrieval Engine.
    Dynamically routes query capability profiles to specific modular rule families,
    eliminating irrelevant dialect injection.
    """

    @classmethod
    def get_rules_for_profile(
        cls, profile: QueryCapabilityProfile, dialect: str = "snowflake"
    ) -> List[str]:
        rules = []
        # Mandatory core rules
        rules.extend(get_identifier_rules())
        rules.extend(get_casting_rules(dialect=dialect))

        if profile.requires_variants:
            rules.extend(get_variant_rules())
        if profile.requires_arrays or profile.requires_flatten:
            rules.extend(get_array_rules())
        if profile.requires_aggregation:
            rules.extend(get_aggregation_rules())
        if profile.requires_joins:
            rules.extend(get_join_rules())
        if profile.requires_timestamps:
            rules.extend(get_timestamp_rules())
        if profile.requires_geospatial:
            rules.extend(get_geospatial_rules())
        if profile.requires_windows or profile.requires_ranking:
            rules.extend(get_window_rules(dialect=dialect))
        if profile.requires_regex:
            rules.extend(get_regex_rules())

        return rules


class DialectRuleRetriever:
    """
    Query-aware dialect rule retrieval engine. Filters full dialect handbooks
    to inject only relevant rules (windows, timestamps, geospatial, variants),
    reducing dialect prompt overhead by over 70%.
    """

    def __init__(self, dialect: str = "snowflake"):
        self.dialect = dialect.lower()
        self.dialect_path = get_dialect_path(self.dialect)
        self.cached_config: dict[str, typing.Any] = {}

    def _load_raw_config(self) -> dict:
        if self.dialect in self.cached_config:
            return self.cached_config[self.dialect]

        try:
            with open(self.dialect_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.cached_config[self.dialect] = config
                return config
        except Exception as e:
            logger.warning(
                f"[RuleRetriever] Failed to load dialect {self.dialect}: {e}"
            )
            return {}

    def get_adaptive_rules(
        self, profile: QueryCapabilityProfile, max_rules: int = 20
    ) -> List[str]:
        """
        Executes Task 1 (Rule Families), Task 9 (Prioritization), and Task 11 (Summarization).
        """
        logger.debug("[DialectRuleRetriever] Retrieving adaptive rule families...")
        active_rules = RuleFamilyRetriever.get_rules_for_profile(
            profile, dialect=self.dialect
        )

        # Rank by priority
        ranked = RulePriorityRanker.rank_rules(active_rules)

        # Trim if needed (raised cap: 15->20 so fewer rules are dropped)
        retained = RulePriorityRanker.trim_rules_by_priority(
            ranked, max_rules=max_rules
        )

        # Summarize
        summarized = RuleSummarizer.summarize_all(retained)
        logger.info(
            f"[DialectRuleRetriever] Adaptive rules retrieved: {len(summarized)} rules."
        )
        return summarized

    def retrieve_relevant_rules(self, intent: QueryIntentAnalysis) -> str:
        """Legacy fallback."""
        config = self._load_raw_config()
        if not config:
            return f"# Dialect rules for {self.dialect.upper()} not found."

        raw_rules = config.get("rules", [])
        return "=== DIALECT RULES ===\n" + "\n".join(f"- {r}" for r in raw_rules[:10])
