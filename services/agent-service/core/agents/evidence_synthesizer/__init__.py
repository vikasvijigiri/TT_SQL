"""
EVIDENCE_SYNTHESIZER -- Agent Package
Combines SQL results with retrieved documents into a coherent evidence package.
"""
from core.agents.evidence_synthesizer.agent import EvidenceSynthesizerAgent
from core.agents.evidence_synthesizer.contract import EvidenceSynthesizerOutput

__all__ = ["EvidenceSynthesizerAgent", "EvidenceSynthesizerOutput"]
