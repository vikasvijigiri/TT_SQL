import os
import sqlite3
import pytest
from core.state import AgentState
from core.workflow_engine import WorkflowEngine
from core.logger import Logger

def test_reference_date_inference():
    # Setup mock DB
    db_path = "test_log.sqlite"
    if os.path.exists(db_path): os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE activity_log (id INT, stamp TEXT)")
    cursor.execute("INSERT INTO activity_log VALUES (1, '2023-05-15 10:00:00')")
    cursor.execute("INSERT INTO activity_log VALUES (2, '2023-06-20 12:00:00')")
    cursor.execute("INSERT INTO activity_log VALUES (3, '2023-06-19 09:00:00')")
    conn.commit()
    conn.close()

    state = AgentState(
        user_query="How many users registered recently?",
        db_path=db_path,
        db_name="test_log",
        dialect="sqlite"
    )
    
    # Mock schema info
    state.full_schema_info = {
        "activity_log": {
            "columns": [
                {"column_name": "id", "type": "INT"},
                {"column_name": "stamp", "type": "TEXT"}
            ]
        }
    }

    # Create dummy workflow.yaml
    dummy_yaml = "dummy_workflow.yaml"
    with open(dummy_yaml, "w") as f:
        f.write("stages: []")

    engine = WorkflowEngine(dummy_yaml, None)
    engine._infer_reference_date(state)
    
    if os.path.exists(dummy_yaml): os.remove(dummy_yaml)

    
    print(f"Inferred Reference Date: {state.reference_date}")
    assert state.reference_date == "2023-06-20"
    
    if os.path.exists(db_path): os.remove(db_path)

if __name__ == "__main__":
    test_reference_date_inference()
