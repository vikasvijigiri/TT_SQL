"""
ANSWER_GENERATOR -- Deterministic Validator
Python logic only. No LLM required.
Uses Pydantic, SQLGlot, or graph analysis depending on agent.
"""
from core.validators.deterministic_validators import DeterministicValidators


class AnswerGeneratorValidator:
    @staticmethod
    def validate(output) -> bool:
        """Run deterministic validation on FinalAnswerOutput."""
        result = DeterministicValidators.validate_answer_generator(output)
        if not result.is_valid:
            raise ValueError(f"[ANSWER_GENERATOR] Validation failed: {result.rejection_reason}")
        return True
