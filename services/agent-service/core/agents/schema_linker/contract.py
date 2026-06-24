"""
SCHEMA_LINKER -- Pydantic Contracts
Selects tables, columns, and value mappings. Enforces coverage threshold.

All inputs and outputs are typed. No free-form dicts.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class SchemaLinkerAgentInput(BaseModel):
    """Input contract for SchemaLinkerAgent."""
    user_query: str = Field(..., description="Raw user question.")
    db_name: Optional[str] = Field(None, description="Target database name.")


class SchemaLinkerOutput(BaseModel):
    """Output contract for SchemaLinkerAgent."""
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in output.")
    reasoning: Optional[str] = Field(None, description="Chain of thought reasoning.")
    rejection_reason: Optional[str] = Field(None, description="Set if validation failed.")
