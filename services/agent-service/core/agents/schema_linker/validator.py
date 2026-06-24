"""
SCHEMA_LINKER -- Deterministic Validator
Python logic only. No LLM required.
Uses Pydantic, SQLGlot, or graph analysis depending on agent.
"""
from core.validators.deterministic_validators import DeterministicValidators


class SchemaLinkerValidator:
    @staticmethod
    def validate(output) -> bool:
        """Run deterministic validation on SchemaLinkerOutput."""
        result = DeterministicValidators.validate_schema_linker(output)
        if not result.is_valid:
            raise ValueError(f"[SCHEMA_LINKER] Validation failed: {result.rejection_reason}")
        return True
