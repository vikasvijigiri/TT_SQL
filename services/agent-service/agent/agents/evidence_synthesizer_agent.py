import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.blackboard.run_blackboard import get_blackboard
from agent.blackboard.dynamic_rules import FailureMemory
from agent.validators.llm_validators import LLMValidators
from agent.telemetry.token_budget import token_budget_enforcer

class EvidenceSynthesizerOutput(BaseModel):
    evidence_summary: str = Field(..., description="Detailed reasoning comparing facts to policies.")
    supporting_facts: List[str] = Field(default_factory=list, description="Extracted facts used for reasoning.")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0")

class EvidenceSynthesizerAgent:
    """
    Executes AFTER the database has been queried to perform Business Reasoning and
    Policy Compliance checking based on the retrieved evidence.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.assembler = PromptAssembler(stage="EVIDENCE_SYNTHESIS")
        self.agent_name = "EVIDENCE_SYNTHESIZER"

    def synthesize(self, user_query: str) -> EvidenceSynthesizerOutput:
        logger.set_agent(self.agent_name)
        bb = get_blackboard()
        logger.info(f"Synthesizing accumulated blackboard evidence for query: {user_query}")

        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=None,
            intent=None
        )

        # Inject Blackboard facts into the user prompt
        evidence_str = ""
        if bb.confirmed_facts:
            evidence_str += "CONFIRMED FACTS:\n"
            for f in bb.confirmed_facts:
                evidence_str += f"- {f['fact']} (Source: {f['source']})\n"
        else:
            evidence_str += "No confirmed facts were accumulated during execution.\n"
            
        full_user_prompt = assembled.user_prompt.replace("{EVIDENCE}", evidence_str)

        response, metrics = self.llm_client.generate(
            system_prompt=assembled.system_prompt,
            user_prompt=full_user_prompt
        )

        logger.record_agent_telemetry(
            agent_name=self.agent_name,
            tokens_in=metrics.get("input_tokens", 0),
            tokens_out=metrics.get("output_tokens", 0),
            latency_ms=metrics.get("latency_ms", 0),
            confidence=1.0,
        )

        token_budget_enforcer.check_budget(
            self.agent_name, 
            metrics.get("input_tokens", 0) + metrics.get("output_tokens", 0)
        )

        try:
            clean_resp = response.strip()
            if clean_resp.startswith("```json"):
                clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp[:-3]
                
            data = json.loads(clean_resp.strip())
            output = EvidenceSynthesizerOutput(**data)
            
            # Semantic Validation Gates
            llm_validators = LLMValidators(self.llm_client)
            
            # Gate 1: Completeness of evidence
            ev_result = llm_validators.validate_evidence(output.evidence_summary)
            if not ev_result.is_valid:
                FailureMemory.record_failure(
                    failure_type="Validation Rejection (Evidence)",
                    root_cause=ev_result.rejection_reason or "Unknown",
                    impact="Evidence does not cover all required facts.",
                    prevention_rule="Trigger document retrieval or modify SQL to pull missing evidence."
                )
                raise ValueError(f"Evidence validation failed: {ev_result.rejection_reason}")

            # Gate 2: Answerability Check (Do not hallucinate)
            ans_result = llm_validators.validate_answerability(output.confidence, output.evidence_summary)
            if not ans_result.is_valid:
                FailureMemory.record_failure(
                    failure_type="Validation Rejection (Answerability)",
                    root_cause=ans_result.rejection_reason or "Unknown",
                    impact="Insufficient concrete facts to answer without hallucination.",
                    prevention_rule="Gather more evidence before calling FinalAnswer."
                )
                raise ValueError(f"Answerability validation failed: {ans_result.rejection_reason}")

            logger.log_parsed_data("Synthesized Evidence", output)
            return output
        except Exception as e:
            logger.error(f"Failed to parse EvidenceSynthesizer output: {e}")
            return EvidenceSynthesizerOutput(
                evidence_summary=f"Failed to synthesize: {e}",
                supporting_facts=[],
                confidence=0.0
            )
