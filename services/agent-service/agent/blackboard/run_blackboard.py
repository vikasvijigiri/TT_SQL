import contextvars
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class RunBlackboardMemory(BaseModel):
    """
    Shared intelligence layer for the entire execution run.
    Survives the entire run and is destroyed afterwards.
    """
    # Upstream Semantic Intent
    question_type: str = ""
    difficulty: str = ""
    goal: str = ""
    
    required_facts: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    required_entities: List[str] = Field(default_factory=list)
    required_metrics: List[str] = Field(default_factory=list)
    answer_strategy: str = ""

    # Schema Validation
    validated_tables: List[str] = Field(default_factory=list)
    validated_columns: List[str] = Field(default_factory=list)
    rejected_tables: List[str] = Field(default_factory=list)
    rejected_columns: List[str] = Field(default_factory=list)

    # Hypotheses
    active_hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    failed_hypotheses: List[Dict[str, Any]] = Field(default_factory=list)

    # Facts Engine
    confirmed_facts: List[Dict[str, Any]] = Field(default_factory=list)
    rejected_facts: List[Dict[str, Any]] = Field(default_factory=list)

    # Temporary Rules & Failures
    temporary_rules: List[Dict[str, Any]] = Field(default_factory=list)
    execution_errors: List[Dict[str, Any]] = Field(default_factory=list)
    recovery_actions: List[str] = Field(default_factory=list)
    failed_sql_strategies: List[str] = Field(default_factory=list)

    # Accumulated Evidence
    evidence: List[str] = Field(default_factory=list)
    agent_feedback: List[str] = Field(default_factory=list)

    # Confidence Tracking
    confidence: Dict[str, float] = Field(default_factory=lambda: {
        "schema": 0.0,
        "sql": 0.0,
        "evidence": 0.0,
        "answer": 0.0
    })

    def format_for_prompt(self) -> str:
        """Serializes relevant blackboard state for agent injection."""
        lines = ["=== CURRENT BLACKBOARD STATE ==="]
        
        if self.goal:
            lines.append(f"Goal: {self.goal}")
        if self.required_facts:
            lines.append(f"Required Facts: {self.required_facts}")
        if self.required_documents:
            lines.append(f"Required Documents: {self.required_documents}")
            
        if self.active_hypotheses:
            lines.append("\nActive Hypotheses:")
            for h in self.active_hypotheses:
                lines.append(f"  - {h['hypothesis']} (Score: {h['score']})")
                
        if self.confirmed_facts:
            lines.append("\nConfirmed Facts:")
            for f in self.confirmed_facts:
                lines.append(f"  - {f['fact']} (Source: {f['source']}, Confidence: {f['confidence']})")
                
        if self.rejected_facts:
            lines.append("\nDisproven Facts (DO NOT USE):")
            for f in self.rejected_facts:
                lines.append(f"  - {f['fact']} (Reason: {f['reason_rejected']})")
                
        if self.temporary_rules:
            lines.append("\nTemporary Execution Rules:")
            for r in self.temporary_rules:
                lines.append(f"  - {r['rule']}")
                
        if self.execution_errors:
            lines.append("\nPrevious Execution Failures:")
            for e in self.execution_errors:
                lines.append(f"  - [{e['failure_type']}] Root Cause: {e['root_cause']}")

        return "\n".join(lines)


# Thread-safe global context variable for the blackboard
# Allows any agent deeper in the stack to read/write the current run's state
# without explicitly passing it through 5 layers of function arguments.
current_blackboard: contextvars.ContextVar[RunBlackboardMemory] = contextvars.ContextVar("current_blackboard")

def get_blackboard() -> RunBlackboardMemory:
    """Safely retrieves the blackboard for the current execution context."""
    try:
        return current_blackboard.get()
    except LookupError:
        # Fallback if accessed outside of a managed run
        return RunBlackboardMemory()
