from typing import Tuple
from backend.app.core.prompts.system_prompt_compactor import SystemPromptCompactor
from backend.app.utils.logger import logger

class PromptBoundaryManager:
    """
    Enterprise Prompt Boundary Manager.
    Enforces strict architectural separation between SYSTEM prompt (static behavioral
    constraints & universal SQL guarantees) and USER prompt (query, schema, retrieved
    rules, and dynamic context).
    """

    @classmethod
    def enforce_boundaries(
        cls,
        raw_system_prompt: str,
        user_sections_text: str,
        user_query: str,
        dialect: str = "SNOWFLAKE"
    ) -> Tuple[str, str]:
        # Compact and isolate system prompt
        clean_sys = SystemPromptCompactor.compact(raw_system_prompt, dialect=dialect)

        # Assemble clean user prompt
        clean_user = f"{user_sections_text.strip()}\n\n=== USER QUERY ===\n<user_query>\n{user_query.strip()}\n</user_query>"

        logger.debug("[PromptBoundaryManager] Enforced strict System vs User boundaries with XML isolation tags.")
        return clean_sys, clean_user
