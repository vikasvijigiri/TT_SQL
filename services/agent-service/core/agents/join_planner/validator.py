"""
JOIN_PLANNER -- Deterministic Validator
Python logic only. No LLM required.
Uses Pydantic, SQLGlot, or graph analysis depending on agent.
"""
from core.validators.deterministic_validators import DeterministicValidators


class JoinPlannerValidator:
    @staticmethod
    def validate(output) -> bool:
        """Run deterministic validation on JoinPlanOutput."""
        result = DeterministicValidators.validate_join_planner(output)
        if not result.is_valid:
            raise ValueError(f"[JOIN_PLANNER] Validation failed: {result.rejection_reason}")
        return True
