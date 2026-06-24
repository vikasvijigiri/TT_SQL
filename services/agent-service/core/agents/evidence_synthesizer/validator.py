"""
EVIDENCE_SYNTHESIZER -- LLM Semantic Validator
Used only because deterministic checks cannot cover semantic completeness.
"""
from core.validators.llm_validators import LLMValidators


class EvidenceSynthesizerValidator:
    def __init__(self, llm_client):
        self._llm = LLMValidators(llm_client)

    def validate(self, output) -> bool:
        result = self._llm.validate_evidence(str(output))
        if not result.is_valid:
            raise ValueError(f"[EVIDENCE_SYNTHESIZER] Validation failed: {result.rejection_reason}")
        return True
