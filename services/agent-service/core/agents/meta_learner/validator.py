"""
META_LEARNER -- Validator
No deterministic gate for this agent. Output is trusted.
"""


class MetaLearnerValidator:
    @staticmethod
    def validate(output) -> bool:
        return True
