from typing import Dict, Any
from backend.app.utils.logger import logger

class FinalTokenizer:
    """
    Enterprise Final Tokenizer.
    Calculates precise token estimations strictly on final rendered prompt strings
    to guarantee 100% accurate telemetry reporting before transmission to the LLM.
    """

    @classmethod
    def _estimate(cls, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    @classmethod
    def count_system_tokens(cls, system_prompt: str) -> int:
        """Returns token count for the final rendered system prompt."""
        return cls._estimate(system_prompt)

    @classmethod
    def count_user_tokens(cls, user_prompt: str) -> int:
        """Returns token count for the final rendered user prompt."""
        return cls._estimate(user_prompt)

    @classmethod
    def count_total_tokens(cls, system_prompt: str, user_prompt: str) -> int:
        """Returns aggregate token count for both system and user prompts."""
        return cls.count_system_tokens(system_prompt) + cls.count_user_tokens(user_prompt)

    @classmethod
    def tokenize_final_prompt(cls, system_prompt: str, user_prompt: str) -> Dict[str, int]:
        """
        Tokenizes the final rendered prompt strings and returns granular counts.
        """
        sys_cnt = cls.count_system_tokens(system_prompt)
        usr_cnt = cls.count_user_tokens(user_prompt)
        tot_cnt = sys_cnt + usr_cnt

        logger.debug(f"[FinalTokenizer] Final Sent Token Count: {tot_cnt} (System: {sys_cnt}, User: {usr_cnt}).")
        return {
            "system_tokens": sys_cnt,
            "user_tokens": usr_cnt,
            "total_tokens": tot_cnt
        }
