"""
QUESTION_ANALYZER -- Pydantic Contracts
Classifies question type, routing, and difficulty. Single responsibility: routing intent.

All inputs and outputs are typed. No free-form dicts.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionAnalyzerAgentInput(BaseModel):
    """Input contract for QuestionAnalyzerAgent."""
    user_query: str = Field(..., description="Raw user question.")
    db_name: Optional[str] = Field(None, description="Target database name.")


class QuestionAnalyzerOutput(BaseModel):
    """Output contract for QuestionAnalyzerAgent."""
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in output.")
    reasoning: Optional[str] = Field(None, description="Chain of thought reasoning.")
    rejection_reason: Optional[str] = Field(None, description="Set if validation failed.")
