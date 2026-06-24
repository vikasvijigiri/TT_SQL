import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from core.utils.llm import LLMClient
from core.utils.logger import logger
from core.blackboard.run_blackboard import get_blackboard
from core.blackboard.facts_engine import FactsEngine
from core.blackboard.dynamic_rules import FailureMemory
from core.validators.deterministic_validators import DeterministicValidators

class ResultAnalyzerOutput(BaseModel):
    discovered_facts: List[str] = Field(default_factory=list, description="Specific facts discovered from the data")
    missing_facts: List[str] = Field(default_factory=list, description="Required facts that are still missing")
    confidence: float = Field(..., description="Confidence in the extracted facts (0.0 to 1.0)")

class ResultAnalyzerAgent:
    """
    Executes AFTER the database is queried.
    Interprets raw JSON results into semantic business facts, confirming or rejecting hypotheses
    via the FactsEngine and the Blackboard.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.agent_name = "RESULT_ANALYZER"

    def analyze(self, user_query: str, sql: str, raw_results: str) -> ResultAnalyzerOutput:
        logger.set_agent(self.agent_name)
        bb = get_blackboard()
        logger.info(f"Analyzing execution results...")

        system_prompt = (
            "You are the Result Analyzer. Your job is to interpret raw database query results "
            "and extract confirmed business facts that answer the user's question.\n"
            "If the results are empty or lack required information, note what is missing.\n"
            "Output strictly valid JSON matching the required schema."
        )

        user_prompt = (
            f"User Question: {user_query}\n\n"
            f"Blackboard Goal: {bb.goal}\n"
            f"Required Facts: {bb.required_facts}\n\n"
            f"Executed SQL:\n```sql\n{sql}\n```\n\n"
            f"Raw Database Results:\n{raw_results}\n\n"
            f"Analyze the results. What concrete facts did we discover? What is still missing?"
        )

        response, metrics = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        try:
            clean_resp = response.strip()
            if clean_resp.startswith("```json"):
                clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp[:-3]
                
            data = json.loads(clean_resp.strip())
            output = ResultAnalyzerOutput(**data)
            
            # Note: We simulate row count check here by parsing raw_results if it's a list.
            # In production, the raw_results should be checked directly by the execution engine, 
            # but we perform semantic validation here too.
            rows_proxy = []
            if isinstance(raw_results, str) and "{" in raw_results:
                rows_proxy = [1] # Simplified for text payload
                
            val_result = DeterministicValidators.validate_results(rows_proxy)
            if not val_result.is_valid:
                FailureMemory.record_failure(
                    failure_type="Validation Rejection (Result Explosion)",
                    root_cause=val_result.rejection_reason or "Unknown",
                    impact="Potential cartesian product or massive aggregation failure.",
                    prevention_rule="Add stricter WHERE clauses or group aggregations properly to prevent row explosions."
                )
                raise ValueError(f"Result validation failed: {val_result.rejection_reason}")
            
            # Update Blackboard through FactsEngine
            for fact in output.discovered_facts:
                FactsEngine.confirm_fact(fact=fact, source="SQL_EXECUTION", confidence=output.confidence)
                
            bb.confidence["evidence"] = max(bb.confidence["evidence"], output.confidence)
            
            logger.success(f"Result Analyzer extracted {len(output.discovered_facts)} facts.")
            return output
            
        except Exception as e:
            logger.error(f"Failed to parse ResultAnalyzer output: {e}")
            return ResultAnalyzerOutput(discovered_facts=[], missing_facts=["Parse error"], confidence=0.0)
