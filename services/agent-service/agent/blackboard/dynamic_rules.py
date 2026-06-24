"""
Dynamic Rule Generator & Failure Memory

Captures failures in real-time and synthesizes temporary prevention rules 
that are immediately injected into the Blackboard for all downstream agents.
"""

from typing import Dict, Any
from agent.services.logger import logger
from agent.blackboard.run_blackboard import get_blackboard

class FailureMemory:
    """Records run-time failures and triggers rule generation."""
    
    @classmethod
    def record_failure(cls, failure_type: str, root_cause: str, impact: str, prevention_rule: str):
        bb = get_blackboard()
        
        failure_record = {
            "failure_type": failure_type,
            "root_cause": root_cause,
            "impact": impact,
            "prevention_rule": prevention_rule
        }
        
        bb.execution_errors.append(failure_record)
        logger.warning(f"[FailureMemory] Recorded failure: {failure_type} | Cause: {root_cause}")
        
        # Immediately generate a temporary rule from this failure
        TemporaryRuleGenerator.generate_rule(
            rule=prevention_rule, 
            scope="current_run", 
            confidence=0.95
        )


class TemporaryRuleGenerator:
    """Generates and manages on-the-fly rules for the current execution run."""
    
    @classmethod
    def generate_rule(cls, rule: str, scope: str = "current_run", confidence: float = 0.95):
        bb = get_blackboard()
        
        # Prevent exact duplicates
        for r in bb.temporary_rules:
            if r["rule"].lower() == rule.lower():
                return
                
        rule_record = {
            "rule": rule,
            "scope": scope,
            "confidence": confidence
        }
        
        bb.temporary_rules.append(rule_record)
        logger.info(f"[TemporaryRuleGenerator] Generated dynamic rule: '{rule}'")
