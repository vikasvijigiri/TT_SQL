from abc import ABC, abstractmethod

from .logger import Logger
from .state import AgentState


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the Text2SQL orchestration layer.

    Provides standardized logging, error handling, and lifecycle management
    for specialized agents (Planning, Generation, Critic, etc.).
    """

    def __init__(self, name: str, config: dict | None = None):
        """
        Initializes a new agent.

        Args:
            name (str): The unique identifier for this agent instance.
            config (dict, optional): Agent-specific configuration overrides.
        """
        self.name = name
        self.config = config or {}

        # Industry standard: extract role and task metadata for prompt injection
        self.role: str = self.config.get("role", "General Assistant")
        self.task: str = self.config.get("task", "perform processing")

    @abstractmethod
    def run(self, state: AgentState) -> AgentState:
        """
        Executes the agent's core logic within the context of a pipeline run.

        Args:
            state (AgentState): The current global state of the analysis pipeline.

        Returns:
            AgentState: The updated global state after agent execution.
        """
        pass

    def log(self, state: AgentState, message: str, level: str = "INFO"):
        """
        Logs a message with the agent's context and persists it to the global state.

        Args:
            state (AgentState): The current pipeline state.
            message (str): The message to log.
            level (str): The logging level (INFO, DEBUG, ERROR, etc.).
        """
        formatted_message = f"[{self.name}]: {message}"
        state.add_log(formatted_message)
        Logger.log(formatted_message, level=level)

    def handle_error(self, state: AgentState, error: Exception) -> AgentState:
        """
        Standardizes error reporting across all agent layers.

        Args:
            state (AgentState): The current pipeline state.
            error (Exception): The exception that occurred.

        Returns:
            AgentState: The state with the error logged.
        """
        error_msg = f"Critical error in agent {self.name}: {str(error)}"
        self.log(state, error_msg, level="ERROR")
        return state
