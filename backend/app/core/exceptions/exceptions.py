class AppError(Exception):
    """Base class for all application-specific errors."""
    def __init__(self, message: str, detail: str = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

class DatabaseError(AppError):
    """Raised when database operations fail."""
    pass

class LLMError(AppError):
    """Raised when LLM service interactions fail."""
    pass

class ConfigurationError(AppError):
    """Raised when environment or project configuration is invalid."""
    pass

class ProjectNotFoundError(AppError):
    """Raised when a requested project does not exist."""
    pass
