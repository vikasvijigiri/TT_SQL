"""
META_LEARNER -- Agent Package
Analyzes cross-run history. Generates permanent rules. Evolves agent prompts.
"""
from core.agents.meta_learner.agent import MetaLearnerAgent
from core.agents.meta_learner.contract import MetaLearnerOutput

__all__ = ["MetaLearnerAgent", "MetaLearnerOutput"]
