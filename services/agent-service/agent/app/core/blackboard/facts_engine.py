"""
Facts Engine

Accumulates confirmed facts and explicitly blocks rejected/disproven facts
during the execution run. Enables the "Evidence Accumulation" principle.
"""

from typing import Dict, Any
from agent.services.logger import logger
from agent.blackboard.run_blackboard import get_blackboard

class FactsEngine:
    
    @classmethod
    def confirm_fact(cls, fact: str, source: str, confidence: float = 1.0):
        bb = get_blackboard()
        
        # Prevent duplicates
        for f in bb.confirmed_facts:
            if f["fact"].lower() == fact.lower():
                # Update confidence if higher
                if confidence > f["confidence"]:
                    f["confidence"] = confidence
                    f["source"] = source
                return
                
        # Check if it was previously rejected. If so, and we have very high confidence now,
        # we might un-reject it, but generally we should be careful.
        for rf in bb.rejected_facts:
            if rf["fact"].lower() == fact.lower():
                logger.warning(f"[FactsEngine] Attempted to confirm fact '{fact}' that was previously REJECTED. Ignoring.")
                return

        fact_record = {
            "fact": fact,
            "source": source,
            "confidence": confidence
        }
        
        bb.confirmed_facts.append(fact_record)
        logger.info(f"[FactsEngine] Confirmed Fact: '{fact}' (Source: {source})")
        
        # Boost confidence in the overall evidence pool
        bb.confidence["evidence"] = min(1.0, bb.confidence["evidence"] + 0.1)

    @classmethod
    def reject_fact(cls, fact: str, reason: str):
        bb = get_blackboard()
        
        # If it was confirmed, remove it
        bb.confirmed_facts = [f for f in bb.confirmed_facts if f["fact"].lower() != fact.lower()]
        
        # Prevent duplicate rejection
        for rf in bb.rejected_facts:
            if rf["fact"].lower() == fact.lower():
                return
                
        reject_record = {
            "fact": fact,
            "reason_rejected": reason
        }
        
        bb.rejected_facts.append(reject_record)
        logger.warning(f"[FactsEngine] Rejected Fact: '{fact}' (Reason: {reason})")
        
        # Penalize confidence
        bb.confidence["evidence"] = max(0.0, bb.confidence["evidence"] - 0.15)
