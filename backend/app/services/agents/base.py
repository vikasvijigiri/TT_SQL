from abc import ABC, abstractmethod
from typing import Any
from app.services.schemas.agent_state import AgentState
from app.services.utils.logger import Logger

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the orchestration layer.
    """
    
    def __init__(self, name: str, config: dict = None, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        self.name = name
        self.config = config or {}
        self.results_dir = results_dir
        self.logs_dir = logs_dir
        self.metadata_dir = metadata_dir

    @abstractmethod
    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
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
