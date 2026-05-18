from typing import Tuple, Set
from backend.app.core.prompts.global_deduplicator import GlobalPromptDeduplicator
from backend.app.utils.logger import logger

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
        keys = set()
        if not system_prompt:
            return keys
            
        for line in system_prompt.splitlines():
            line_str = line.strip()
            if len(line_str) > 10:
                k = GlobalPromptDeduplicator.get_core_semantic_key(line_str)
                if len(k) > 5:
                    keys.add(k)
        return keys

    @classmethod
    def split_and_clean(cls, system_prompt: str, user_prompt: str) -> Tuple[str, str, int]:
        """
        Deduplicates user prompt content against system prompt instructions to guarantee zero overlap.
        Returns clean system prompt, clean user prompt, and total tokens saved.
        """
        if not system_prompt or not user_prompt:
            return system_prompt, user_prompt, 0

        sys_keys = cls.extract_system_keys(system_prompt)
        if not sys_keys:
            return system_prompt, user_prompt, 0

        clean_user_lines, savings = GlobalPromptDeduplicator.deduplicate_lines(user_prompt.splitlines(), sys_keys, similarity_threshold=0.85)
        clean_user_prompt = "\n".join(clean_user_lines).strip()
        
        if savings > 0:
            logger.debug(f"[ResponsibilitySplitter] Suppressed ~{savings} tokens of system/user prompt overlap.")

        return system_prompt.strip(), clean_user_prompt, savings
