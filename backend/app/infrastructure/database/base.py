from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

@dataclass
class QueryResult:
    columns: List[str] = None
    rows: List[List[Any]] = None
    row_count: int = 0
    error_message: Optional[str] = None

class DatabaseConnector(ABC):
    """Abstract base class for all database engine implementations."""
    
    @abstractmethod
    def execute(self, query: str) -> QueryResult:
        """Execute a raw SQL query and return a QueryResult."""
        pass

    @abstractmethod
    def check_connection(self) -> bool:
        """Verify if the connection can be established."""
        pass
