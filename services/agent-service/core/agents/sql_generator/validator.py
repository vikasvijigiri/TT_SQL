"""
SQL_GENERATOR -- Deterministic Validator
Python logic only. No LLM required.
Uses Pydantic, SQLGlot, or graph analysis depending on agent.
"""
from core.validators.deterministic_validators import DeterministicValidators


class SqlGeneratorValidator:
    @staticmethod
    def validate(output) -> bool:
        """Run deterministic validation on SQLGeneratorOutput."""
        result = DeterministicValidators.validate_sql_generator(output)
        if not result.is_valid:
            raise ValueError(f"[SQL_GENERATOR] Validation failed: {result.rejection_reason}")
        return True
