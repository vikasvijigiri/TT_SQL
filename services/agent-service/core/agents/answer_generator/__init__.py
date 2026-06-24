"""
ANSWER_GENERATOR -- Agent Package
Formats the final answer. No SQL. No retrieval. Purely formats evidence into answer.
"""
from core.agents.answer_generator.agent import FinalAnswerAgent
from core.agents.answer_generator.contract import FinalAnswerOutput

__all__ = ["FinalAnswerAgent", "FinalAnswerOutput"]
