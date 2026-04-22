import pytest
from core.state import AgentState, ExecutionResult

def test_agent_state_initialization():
    """Verify that AgentState initializes with correct defaults."""
    state = AgentState(user_query="test", db_path="test.db")
    assert state.user_query == "test"
    assert state.db_path == "test.db"
    assert state.current_step == "INIT"
    assert state.is_result_valid is False

def test_execution_result_to_df():
    """Verify ExecutionResult conversion to pandas DataFrame."""
    try:
        import pandas as pd
        res = ExecutionResult(
            columns=["id", "name"],
            rows=[[1, "Alice"], [2, "Bob"]]
        )
        df = res.rows_to_df()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["id", "name"]
    except ImportError:
        pytest.skip("Pandas not installed")

def test_state_add_log():
    """Verify logging functionality in AgentState."""
    state = AgentState(user_query="test", db_path="test.db")
    state.add_log("Starting test")
    assert len(state.logs) == 1
    assert state.logs[0] == "Starting test"
