"""
SEMANTIC_PLANNER -- Deterministic Validator
Python logic only. No LLM required.
Uses Pydantic, SQLGlot, or graph analysis depending on agent.
"""
from core.validators.deterministic_validators import DeterministicValidators


class SemanticPlannerValidator:
    @staticmethod
    def validate(output) -> bool:
        """Run deterministic validation on SemanticPlannerOutput."""
        result = DeterministicValidators.validate_semantic_planner(output)
        if not result.is_valid:
            raise ValueError(f"[SEMANTIC_PLANNER] Validation failed: {result.rejection_reason}")
        return True
