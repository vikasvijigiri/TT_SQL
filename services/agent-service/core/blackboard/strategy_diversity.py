"""
Strategy Diversity Manager (Anti-Repetition Engine)

Prevents retry loops by comparing proposed strategies (e.g. SQL queries)
against previously failed strategies. If similarity exceeds the threshold (0.85),
the strategy is rejected.
"""

import math
from collections import Counter
from core.utils.logger import logger
from core.blackboard.run_blackboard import get_blackboard

class StrategyDiversityManager:
    SIMILARITY_THRESHOLD = 0.85

    @staticmethod
    def _compute_cosine_similarity(text1: str, text2: str) -> float:
        """Simple Bag-of-Words Cosine Similarity."""
        import re
        def get_words(text):
            words = re.compile(r'\w+').findall(text.lower())
            return Counter(words)

        vec1 = get_words(text1)
        vec2 = get_words(text2)
        
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum([vec1[x] * vec2[x] for x in intersection])
        
        sum1 = sum([vec1[x]**2 for x in vec1.keys()])
        sum2 = sum([vec2[x]**2 for x in vec2.keys()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        
        if not denominator:
            return 0.0
        return float(numerator) / denominator

    @classmethod
    def register_failed_strategy(cls, strategy: str):
        """Record a failed strategy (e.g. a SQL query) in the blackboard."""
        bb = get_blackboard()
        if strategy not in bb.failed_sql_strategies:
            bb.failed_sql_strategies.append(strategy)
            logger.debug("[StrategyDiversityManager] Registered failed strategy.")

    @classmethod
    def is_strategy_too_similar(cls, proposed_strategy: str) -> bool:
        """
        Check if the proposed strategy is too similar to any previously failed strategy.
        Returns True if it violates the diversity threshold.
        """
        bb = get_blackboard()
        
        if not bb.failed_sql_strategies:
            return False

        for failed in bb.failed_sql_strategies:
            score = cls._compute_cosine_similarity(proposed_strategy, failed)
            if score >= cls.SIMILARITY_THRESHOLD:
                logger.warning(
                    f"[StrategyDiversityManager] Proposed strategy rejected! "
                    f"Similarity score {score:.2f} >= {cls.SIMILARITY_THRESHOLD} threshold."
                )
                return True
                
        return False
