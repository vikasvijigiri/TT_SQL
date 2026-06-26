"""
V4 Validation Engine (LLM-Backed)

Contains LLM validators for semantic checks that cannot be performed deterministically.
These are more expensive and should only be used after deterministic gates pass.
"""
import json
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.models.schemas import EvidenceValidatorOutput, AnswerabilityValidatorOutput
from agent.blackboard.run_blackboard import get_blackboard

class LLMValidators:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def validate_evidence(self, synthesized_evidence: str) -> EvidenceValidatorOutput:
        bb = get_blackboard()
        system_prompt = (
            "You are the Evidence Validator. Your job is to verify if the retrieved "
            "and synthesized evidence completely covers the required facts and documents.\n"
            "Output strictly valid JSON."
        )
        user_prompt = (
            f"Goal: {bb.goal}\n"
            f"Required Facts: {bb.required_facts}\n"
            f"Required Documents: {bb.required_documents}\n\n"
            f"Synthesized Evidence:\n{synthesized_evidence}\n\n"
            f"Are we missing any required facts or documents?"
        )
        
        response, _ = self.llm_client.generate(system_prompt, user_prompt)
        try:
            clean = response.strip()
            if clean.startswith("```json"): clean = clean[7:]
            if clean.endswith("```"): clean = clean[:-3]
            
            # Simple heuristic for now: ask LLM to output {"is_valid": bool, "rejection_reason": ""}
            # For simplicity, if the LLM says "missing", we reject.
            if "missing" in clean.lower():
                return EvidenceValidatorOutput(is_valid=False, rejection_reason="Evidence incomplete based on LLM review.")
            return EvidenceValidatorOutput(is_valid=True)
        except Exception:
            return EvidenceValidatorOutput(is_valid=True) # Fail open if parsing fails

    def validate_answerability(self, confidence: float, evidence: str) -> AnswerabilityValidatorOutput:
        """Determines if we have enough concrete facts to answer without hallucinating."""
        bb = get_blackboard()
        system_prompt = (
            "You are the Answerability Validator. Determine if the question can be "
            "factually answered based ONLY on the provided evidence. Do not guess.\n"
            "Output strictly valid JSON with is_valid and rejection_reason."
        )
        user_prompt = (
            f"Question: {bb.question_type}\n"
            f"Evidence:\n{evidence}\n\n"
            f"Can this be fully answered?"
        )
        
        # If deterministic confidence is high enough, skip LLM check to save tokens
        if confidence > 0.90:
            return AnswerabilityValidatorOutput(is_valid=True)
            
        response, _ = self.llm_client.generate(system_prompt, user_prompt)
        try:
            clean = response.strip()
            if "false" in clean.lower():
                return AnswerabilityValidatorOutput(is_valid=False, rejection_reason="Cannot answer without hallucinating.")
            return AnswerabilityValidatorOutput(is_valid=True)
        except Exception:
            return AnswerabilityValidatorOutput(is_valid=True)
