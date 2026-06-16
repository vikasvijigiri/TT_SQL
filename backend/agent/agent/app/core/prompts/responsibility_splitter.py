import typing
from typing import Set
from agent.app.core.prompts.global_deduplicator import GlobalPromptDeduplicator


class PromptResponsibilitySplitter:
    """
    Enterprise Prompt Responsibility Splitter.
    Enforces a strict architectural division of labor:
    - SYSTEM prompt: Behavioral constraints, hallucination prevention, output formatting contracts.
    - USER prompt: Dynamic database schema, query, retrieved dialect rules, and syntax templates.
    Never duplicates content across both boundaries.
    """

    @classmethod
    def extract_system_keys(cls, system_prompt: str) -> Set[str]:
        """Extracts canonical semantic keys from all instructional lines in the system prompt."""
        keys: set[str] = set()
        if not system_prompt:
            return keys

        for line in system_prompt.splitlines():
            line_str = line.strip()
            if len(line_str) > 10:
                k = GlobalPromptDeduplicator.get_core_semantic_key(line_str)
                if len(k) > 5:
                    keys.add(k)
        return keys
