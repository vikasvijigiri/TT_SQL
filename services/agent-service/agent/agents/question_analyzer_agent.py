import json
from typing import Dict, Any
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.telemetry.token_budget import token_budget_enforcer
from agent.blackboard.run_blackboard import get_blackboard
from agent.blackboard.dynamic_rules import FailureMemory
from agent.validators.deterministic_validators import DeterministicValidators

class QuestionAnalyzerOutput(BaseModel):
    question_type: str = Field(..., description="The type of the query")
    difficulty: str = Field(..., description="The complexity level")
    requires_sql: bool = Field(..., description="Whether SQL execution is needed")
    requires_retrieval: bool = Field(..., description="Whether document retrieval is needed")
    requires_business_reasoning: bool = Field(..., description="Whether business rules/policy evaluation is needed")
    requires_multi_db: bool = Field(..., description="Whether cross-database querying is expected")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0")

class QuestionAnalyzerAgent:
    """
    Executes BEFORE schema linking to deeply understand the problem.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.assembler = PromptAssembler(stage="QUESTION_ANALYSIS")
        self.agent_name = "QUESTION_ANALYZER"

    def analyze(self, user_query: str) -> QuestionAnalyzerOutput:
        logger.set_agent(self.agent_name)
        logger.info(f"Analyzing question: {user_query}")

        # Assemble Prompt (bypasses full schema loading since we don't need it yet)
        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=None,
            intent=None
        )

        response, metrics = self.llm_client.generate(
            system_prompt=assembled.system_prompt,
            user_prompt=assembled.user_prompt
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
            # Clean response
            clean_resp = response.strip()
            if clean_resp.startswith("```json"):
                clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp[:-3]
                
            data = json.loads(clean_resp.strip())
            output = QuestionAnalyzerOutput(**data)
            
            # Deterministic Validation Gate
            val_result = DeterministicValidators.validate_question(output)
            if not val_result.is_valid:
                FailureMemory.record_failure(
                    failure_type="Validation Rejection (Question)",
                    root_cause=val_result.rejection_reason or "Unknown",
                    impact="Question analysis invalid, cannot proceed.",
                    prevention_rule="Ensure confidence is high and question type is accurately classified."
                )
                raise ValueError(f"Question validation failed: {val_result.rejection_reason}")
            
            # Write to Blackboard
            bb = get_blackboard()
            bb.question_type = output.question_type
            bb.difficulty = output.difficulty
            
            logger.log_parsed_data("Question Analysis", output)
            return output
        except Exception as e:
            logger.error(f"Failed to parse QuestionAnalyzer output: {e}")
            # Fallback
            return QuestionAnalyzerOutput(
                question_type="UNKNOWN",
                difficulty="MEDIUM",
                requires_sql=True,
                requires_retrieval=False,
                requires_business_reasoning=False,
                requires_multi_db=False,
                confidence=0.0
            )
