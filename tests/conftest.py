import pytest
from core.state import AgentState
from core.llm_service import LLMService

@pytest.fixture
def sample_state():
    """Provides a basic AgentState for testing."""
    return AgentState(
        user_query="What is the average age of users?",
        db_path=":memory:",
        instance_id="test_001"
    )

@pytest.fixture
def mock_llm():
    """A mock LLM service that returns predefined responses."""
    class MockLLM:
        def get_completion(self, messages, **kwargs):
            return "SUCCESS"
        
        def get_json_completion(self, messages, **kwargs):
            return {"status": "success", "sql": "SELECT 1"}
            
    return MockLLM()
