"""
Token Budget Enforcer

Enforces hard token limits per agent as per the new Enterprise Architecture.
Fails safe and logs violations when exceeded.
"""
from typing import Dict, Optional

class TokenBudgetExceededError(Exception):
    """Raised when an agent exceeds its hard token budget."""
    pass

class TokenBudgetEnforcer:
    # Hard limits defined in the Enterprise Architecture
    BUDGETS: Dict[str, int] = {
        "QUESTION_ANALYZER": 500,
        "SEMANTIC_PLANNER": 800,
        "SCHEMA_LINKER": 1500,
        "SQL_GENERATOR": 2000,
        "SQL_CRITIC": 1000,
        "EVIDENCE_SYNTHESIZER": 1500,
        "FINAL_ANSWER": 500
    }
    
    @classmethod
    def check_budget(cls, agent_name: str, total_tokens: int) -> bool:
        """
        Check if the token count exceeds the budget for the specified agent.
        Raises TokenBudgetExceededError if it does.
        """
        agent_upper = agent_name.upper().strip()
        
        # If the agent doesn't have a specific budget, apply a default fallback or allow it
        budget = cls.BUDGETS.get(agent_upper)
        if not budget:
            return True
            
        if total_tokens > budget:
            raise TokenBudgetExceededError(
                f"Agent {agent_upper} exceeded its token budget! "
                f"Limit: {budget}, Actual: {total_tokens}"
            )
            
        return True

    @classmethod
    def get_budget(cls, agent_name: str) -> Optional[int]:
        """Get the hard limit for an agent."""
        return cls.BUDGETS.get(agent_name.upper().strip())

# Singleton export
token_budget_enforcer = TokenBudgetEnforcer()
