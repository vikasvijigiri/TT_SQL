from abc import ABC, abstractmethod
from typing import Any, Optional
from app.schemas.agent_state import AgentState
from app.core.logging.logger import Logger

class BaseAgent(ABC):
    """
    Abstract base class for all domain agents.
    Provides standardized logging, error handling, and state management hooks.
    """
    def __init__(self, name: str, user_slug: Optional[str] = None, project_slug: Optional[str] = None, **kwargs):
        self.name = name
        self.user_slug = user_slug
        self.project_slug = project_slug
        self.config = kwargs

    @abstractmethod
    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        """Core execution logic to be implemented by concrete agents."""
        pass
    
    def log(self, state: AgentState, message: str, level: str = "INFO"):
        """Standardized agent-prefixed logging."""
        entry = f"[{self.name}]: {message}"
        state.logs.append(entry)
        Logger.log(entry, level=level)

    def handle_error(self, state: AgentState, error: Exception) -> AgentState:
        """Centralized error reporting and state recovery entry point."""
        msg = f"Agent {self.name} failed: {error}"
        self.log(state, msg, level="ERROR")
        state.error_message = msg
        return state
