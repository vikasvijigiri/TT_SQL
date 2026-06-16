from typing import List, Any
from agent.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from agent.app.utils.logger import logger


class PromptQualityGuard:
    """
    Enterprise Prompt Quality Preservation Guard.
    Audits assembled prompt sections/nodes before final compilation to detect overcompression
    or missing critical safeguards and selectively re-injects required syntax guidance.
    Supports both PromptSection and PromptNode objects.
    """

    VARIANT_SAFEGUARD_TEXT = (
        '- [CRITICAL] Access VARIANT object keys via colon notation ("col":"key"::TYPE) or GET_PATH. '
        "Always apply explicit cast ::TYPE. Never use dot notation."
    )
    JOIN_SAFEGUARD_TEXT = (
        "- [CRITICAL] Verify every JOIN predicate references existing FK/PK columns verbatim from SCHEMA. "
        "Use COALESCE to handle NULLs in outer join columns before comparison."
    )
    AGGREGATION_SAFEGUARD_TEXT = (
        "- [CRITICAL] All non-aggregated SELECT columns must appear in GROUP BY. "
        "Apply NULLIF(denominator, 0) in every division expression to prevent runtime errors."
    )
    TIMESTAMP_SAFEGUARD_TEXT = (
        "- [CRITICAL] Use dialect-native date functions only. "
        "Avoid mixing EXTRACT(EPOCH), epoch_ms(), DATEDIFF, and DATE_ADD across dialects."
    )
    GEOSPATIAL_SAFEGUARD_TEXT = (
        "- [CRITICAL] Apply ST_* functions (ST_Distance, ST_Within, ST_Contains) with matching SRID. "
        "Cast geometry columns to GEOGRAPHY before distance calculations."
    )

    @classmethod
    def _get_content(cls, node: Any) -> str:
        raw = getattr(node, "content", "")
        return raw if isinstance(raw, str) else str(raw)

    @classmethod
    def _inject(cls, nodes: List[Any], rules_node: Any, text: str) -> None:
        """Append `text` to the existing rules node or create a new one."""
        if rules_node and isinstance(rules_node.content, str):
            rules_node.content += f"\n{text}"
        elif not rules_node:
            if nodes and hasattr(nodes[0], "section_type"):
                from agent.app.core.prompts.prompt_ast import PromptNode

                new_node = PromptNode(
                    name="dialect_rules",
                    section_type="rules",
                    content=f"=== RE-EXPANDED DIALECT RULES ===\n{text}",
                    priority=1,
                    droppable=False,
                )
            else:
                from agent.app.core.prompts.prompt_sections import PromptSection

                new_node = PromptSection(  # type: ignore
                    name="dialect_rules",
                    content=f"=== RE-EXPANDED DIALECT RULES ===\n{text}",
                    priority=1,
                    droppable=False,
                )
            nodes.insert(1, new_node)

    @classmethod
    def audit_and_safeguard(
        cls,
        nodes: List[Any],
        profile: QueryCapabilityProfile,
        dropped_names: List[str],
        dialect: str = "snowflake",
    ) -> List[Any]:
        rules_node = next((n for n in nodes if n.name == "dialect_rules"), None)
        content_str = cls._get_content(rules_node) if rules_node else ""
        d = dialect.lower()

        # 1. Variant safeguard
        if profile.requires_variants and "variant" not in content_str.lower():
            logger.warning("[PromptQualityGuard] Variant rules missing Ã¢â‚¬â€ re-injecting.")
            text = cls.VARIANT_SAFEGUARD_TEXT
            if d == "sqlite":
                text = text.replace("::TYPE", "CAST(... AS TYPE)")
            cls._inject(nodes, rules_node, text)
            content_str += "\n" + text
            rules_node = next((n for n in nodes if n.name == "dialect_rules"), None)

        # 2. Join safeguard
        if profile.requires_joins and "join predicate" not in content_str.lower():
            logger.warning("[PromptQualityGuard] Join rules missing Ã¢â‚¬â€ re-injecting.")
            cls._inject(nodes, rules_node, cls.JOIN_SAFEGUARD_TEXT)
            content_str += "\n" + cls.JOIN_SAFEGUARD_TEXT
            rules_node = next((n for n in nodes if n.name == "dialect_rules"), None)

        # 3. Aggregation safeguard
        if profile.requires_aggregation and "group by" not in content_str.lower():
            logger.warning(
                "[PromptQualityGuard] Aggregation rules missing Ã¢â‚¬â€ re-injecting."
            )
            cls._inject(nodes, rules_node, cls.AGGREGATION_SAFEGUARD_TEXT)
            content_str += "\n" + cls.AGGREGATION_SAFEGUARD_TEXT
            rules_node = next((n for n in nodes if n.name == "dialect_rules"), None)

        # 4. Timestamp safeguard
        if profile.requires_timestamps and "date" not in content_str.lower():
            logger.warning(
                "[PromptQualityGuard] Timestamp rules missing Ã¢â‚¬â€ re-injecting."
            )
            cls._inject(nodes, rules_node, cls.TIMESTAMP_SAFEGUARD_TEXT)
            content_str += "\n" + cls.TIMESTAMP_SAFEGUARD_TEXT
            rules_node = next((n for n in nodes if n.name == "dialect_rules"), None)

        # 5. Geospatial safeguard
        if (
            getattr(profile, "requires_geospatial", False)
            and "st_" not in content_str.lower()
        ):
            logger.warning(
                "[PromptQualityGuard] Geospatial rules missing Ã¢â‚¬â€ re-injecting."
            )
            cls._inject(nodes, rules_node, cls.GEOSPATIAL_SAFEGUARD_TEXT)
            content_str += "\n" + cls.GEOSPATIAL_SAFEGUARD_TEXT
            rules_node = next((n for n in nodes if n.name == "dialect_rules"), None)

        # 6. Guard against dialect_rules being dropped entirely
        if "dialect_rules" in dropped_names:
            logger.warning(
                "[PromptQualityGuard] 'dialect_rules' was dropped entirely Ã¢â‚¬â€ re-injecting minimal baseline."
            )
            minimal_rules = (
                "=== CRITICAL DIALECT RULES ===\n"
                "- Double-quote identifiers matching SCHEMA casing.\n"
                "- Semicolon termination."
            )
            if nodes and hasattr(nodes[0], "section_type"):
                from agent.app.core.prompts.prompt_ast import PromptNode

                nodes.append(
                    PromptNode(
                        name="dialect_rules",
                        section_type="rules",
                        content=minimal_rules,
                        priority=1,
                        droppable=False,
                    )
                )
            else:
                from agent.app.core.prompts.prompt_sections import PromptSection

                nodes.append(
                    PromptSection(
                        name="dialect_rules",
                        content=minimal_rules,
                        priority=1,
                        droppable=False,
                    )
                )
            dropped_names.remove("dialect_rules")

        return nodes
