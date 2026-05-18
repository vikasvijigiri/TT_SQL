from typing import List, Any
from backend.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from backend.app.utils.logger import logger

class PromptQualityGuard:
    """
    Enterprise Prompt Quality Preservation Guard.
    Audits assembled prompt sections/nodes before final compilation to detect overcompression
    or missing critical safeguards (e.g. variant syntax on a variant-heavy query)
    and selectively re-expands or injects required syntax guidance.
    Supports both PromptSection and PromptNode objects.
    """

    VARIANT_SAFEGUARD_TEXT = "- [CRITICAL] Access VARIANT object keys via colon notation (\"col\":\"key\"::TYPE) or GET_PATH. Always apply explicit cast ::TYPE. Never use dot notation."

    @classmethod
    def audit_and_safeguard(
        cls,
        nodes: List[Any],
        profile: QueryCapabilityProfile,
        dropped_names: List[str]
    ) -> List[Any]:
        rules_node = next((n for n in nodes if n.name == "dialect_rules"), None)
        
        # 1. Audit Variant Safeguard
        if profile.requires_variants:
            content_str = getattr(rules_node, 'content', '') if isinstance(getattr(rules_node, 'content', ''), str) else str(getattr(rules_node, 'content', ''))
            if not rules_node or "variant" not in content_str.lower():
                logger.warning("[PromptQualityGuard] Quality Risk: Detected variant-heavy query but variant rules were overcompressed or missing. Re-injecting critical variant safeguard.")
                if rules_node and isinstance(rules_node.content, str):
                    rules_node.content += f"\n{cls.VARIANT_SAFEGUARD_TEXT}"
                elif not rules_node:
                    # Determine constructor based on type of first item if available
                    if nodes and hasattr(nodes[0], 'section_type'):
                        from backend.app.core.prompts.prompt_ast import PromptNode
                        new_node = PromptNode(name="dialect_rules", section_type="rules", content=f"=== RE-EXPANDED DIALECT RULES ===\n{cls.VARIANT_SAFEGUARD_TEXT}", priority=1, droppable=False)
                    else:
                        from backend.app.core.prompts.prompt_sections import PromptSection
                        new_node = PromptSection(name="dialect_rules", content=f"=== RE-EXPANDED DIALECT RULES ===\n{cls.VARIANT_SAFEGUARD_TEXT}", priority=1, droppable=False)
                    nodes.insert(1, new_node)

        # 2. Audit Missing Core Sections
        if "dialect_rules" in dropped_names:
            logger.warning("[PromptQualityGuard] Quality Risk: 'dialect_rules' was dropped entirely. Re-injecting minimal syntax baseline.")
            minimal_rules = "=== CRITICAL DIALECT RULES ===\n- Double-quote identifiers matching SCHEMA casing.\n- Semicolon termination."
            if nodes and hasattr(nodes[0], 'section_type'):
                from backend.app.core.prompts.prompt_ast import PromptNode
                nodes.append(PromptNode(name="dialect_rules", section_type="rules", content=minimal_rules, priority=1, droppable=False))
            else:
                from backend.app.core.prompts.prompt_sections import PromptSection
                nodes.append(PromptSection(name="dialect_rules", content=minimal_rules, priority=1, droppable=False))
            if "dialect_rules" in dropped_names:
                dropped_names.remove("dialect_rules")

        return nodes
