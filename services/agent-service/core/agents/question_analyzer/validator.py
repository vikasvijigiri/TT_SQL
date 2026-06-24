"""
QUESTION_ANALYZER -- Deterministic Validator
Python logic only. No LLM required.
Uses Pydantic, SQLGlot, or graph analysis depending on agent.
"""
from core.validators.deterministic_validators import DeterministicValidators


class QuestionAnalyzerValidator:
    @staticmethod
    def validate(output) -> bool:
        """Run deterministic validation on QuestionAnalyzerOutput."""
        result = DeterministicValidators.validate_question_analyzer(output)
        if not result.is_valid:
            raise ValueError(f"[QUESTION_ANALYZER] Validation failed: {result.rejection_reason}")
        return True
