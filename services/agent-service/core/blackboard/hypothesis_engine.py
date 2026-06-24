"""
Hypothesis Engine

Tracks competing hypotheses during a run.
Updates scores as evidence appears or is disproved.
Deactivates hypotheses that fall below the threshold.
"""

from typing import List, Dict, Any
from core.utils.logger import logger
from core.blackboard.run_blackboard import get_blackboard

class HypothesisManager:
    """Manages hypotheses within the current run blackboard."""
    
    DEACTIVATION_THRESHOLD = 0.2

    @classmethod
    def propose_hypothesis(cls, hypothesis: str, initial_score: float = 0.5):
        """Propose a new hypothesis and store it in the blackboard."""
        bb = get_blackboard()
        
        # Check if already exists
        for h in bb.active_hypotheses:
            if h["hypothesis"].lower() == hypothesis.lower():
                return
                
        h_record = {
            "hypothesis": hypothesis,
            "score": initial_score,
            "status": "active"
        }
        bb.active_hypotheses.append(h_record)
        logger.info(f"[HypothesisManager] Proposed new hypothesis: '{hypothesis}' (score: {initial_score})")

    @classmethod
    def evaluate_evidence(cls, hypothesis: str, supports: bool, weight: float = 0.2):
        """
        Update the score of a hypothesis based on new evidence.
        If it falls below the threshold, move it to failed_hypotheses.
        """
        bb = get_blackboard()
        
        target = None
        for h in bb.active_hypotheses:
            # Simple substring match for linking evidence to hypothesis
            if hypothesis.lower() in h["hypothesis"].lower() or h["hypothesis"].lower() in hypothesis.lower():
                target = h
                break
                
        if not target:
            return

        old_score = target["score"]
        if supports:
            target["score"] = min(1.0, old_score + weight)
            logger.info(f"[HypothesisManager] Evidence SUPPORTS hypothesis '{target['hypothesis']}'. Score: {old_score:.2f} -> {target['score']:.2f}")
        else:
            target["score"] = max(0.0, old_score - weight)
            logger.info(f"[HypothesisManager] Evidence DISPROVES hypothesis '{target['hypothesis']}'. Score: {old_score:.2f} -> {target['score']:.2f}")

        # Check threshold
        if target["score"] < cls.DEACTIVATION_THRESHOLD:
            target["status"] = "failed"
            bb.active_hypotheses.remove(target)
            bb.failed_hypotheses.append(target)
            logger.warning(f"[HypothesisManager] Hypothesis '{target['hypothesis']}' deactivated (score below threshold).")
            
    @classmethod
    def get_active_hypotheses(cls) -> List[str]:
        bb = get_blackboard()
        return [h["hypothesis"] for h in bb.active_hypotheses]
