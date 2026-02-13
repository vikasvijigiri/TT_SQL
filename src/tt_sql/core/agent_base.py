from abc import ABC, abstractmethod
from typing import Any
from .state import AgentState
from .logger import Logger

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the orchestration layer.
    """
    
    def __init__(self, name: str, config: dict = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def run(self, state: AgentState) -> AgentState:
        """
        Execute the agent's logic.
        
        Args:
            state: The current global state.
            
        Returns:
            The updated global state.
        """
        pass
    
    def log(self, state: AgentState, message: str, level: str = "INFO"):
        """Helper to add log with agent context."""
        formatted_message = f"[{self.name}]: {message}"
        state.add_log(formatted_message)
        Logger.log(formatted_message, level=level)

    def handle_error(self, state: AgentState, error: Exception) -> AgentState:
        """Standard error handling."""
        error_msg = f"Error in agent {self.name}: {str(error)}"
        self.log(state, error_msg)
        # Depending on severity, we might want to flag a state error
        return state
