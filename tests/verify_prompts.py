import sys
import os

# Add src to pythonpath
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, '../src'))

from tt_sql.core.prompt_loader import PromptLoader

def test_prompts():
    loader = PromptLoader()
    
    print("Testing PromptLoader...")
    
    # Test 1: sqlite_generation
    try:
        msgs = loader.load_prompt("sqlite_generation", schema_summary="{}", user_query="test", step_by_step_plan="plan")
        print(f"[OK] sqlite_generation: {len(msgs)} messages")
    except Exception as e:
        print(f"[FAIL] sqlite_generation: {e}")

    # Test 2: error_correction
    try:
        msgs = loader.load_prompt("error_correction", sql="SELECT 1", error="error", tables_available="[]")
        print(f"[OK] error_correction: {len(msgs)} messages")
    except Exception as e:
        print(f"[FAIL] error_correction: {e}")

    # Test 3: intent_classification
    try:
        msgs = loader.load_prompt("intent_classification", user_query="test")
        print(f"[OK] intent_classification: {len(msgs)} messages")
    except Exception as e:
        print(f"[FAIL] intent_classification: {e}")

    # Test 4: table_selection
    try:
        msgs = loader.load_prompt("table_selection", user_query="test", all_tables="table1")
        print(f"[OK] table_selection: {len(msgs)} messages")
    except Exception as e:
        print(f"[FAIL] table_selection: {e}")

    # Test 5: query_planning
    try:
        msgs = loader.load_prompt("query_planning", user_query="test", relevant_tables="['table1']")
        print(f"[OK] query_planning: {len(msgs)} messages")
    except Exception as e:
        print(f"[FAIL] query_planning: {e}")

if __name__ == "__main__":
    test_prompts()
