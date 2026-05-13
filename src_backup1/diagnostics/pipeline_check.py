import os
import json
import asyncio
from typing import Dict, Any
from pydantic import ValidationError
from src.core.models import FullPlan, CriticResult, SQLBuilderOutput
from src.validation.sql_validator import SQLValidator
from src.utils.data_iq import analyze_result
from src.utils.prompt_loader import PromptLoader
from src.utils.llm import LLMService

async def test_pydantic_models():
    print("Testing Pydantic Models...")
    
    # 1. FullPlan
    valid_plan = {
        "strategies": {"primary": []},
        "requested_tables": ["TABLE1"]
    }
    try:
        FullPlan.model_validate(valid_plan)
        print("[PASS] FullPlan (Simple)")
    except ValidationError as e:
        print(f"[FAIL] FullPlan (Simple): {e}")

    # 2. CriticResult
    valid_critic = {
        "is_valid": True,
        "logical_fit": "pass",
        "feedback": "Good job"
    }
    try:
        CriticResult.model_validate(valid_critic)
        print("[PASS] CriticResult")
    except ValidationError as e:
        print(f"[FAIL] CriticResult: {e}")

    # 3. SQLBuilderOutput
    valid_sql = {
        "candidates": [{"id": 1, "reasoning": "r", "sql": "SELECT 1"}],
        "sql": "SELECT 1"
    }
    try:
        SQLBuilderOutput.model_validate(valid_sql)
        print("[PASS] SQLBuilderOutput")
    except ValidationError as e:
        print(f"[FAIL] SQLBuilderOutput: {e}")

def test_sql_validator():
    print("\nTesting SQLValidator (Non-LLM)...")
    validator = SQLValidator(db_connector=None) # Mock DB
    
    # Syntax check
    valid_sql = "SELECT * FROM my_table WHERE id = 1"
    err = validator._check_syntax(valid_sql, "snowflake")
    if err:
        print(f"[FAIL] SQL Syntax Check: {err}")
    else:
        print("[PASS] SQL Syntax Check")

    invalid_sql = "SELECT * FROM WHERE id = 1" # Missing column/star
    err = validator._check_syntax(invalid_sql, "snowflake")
    if err:
        print(f"[PASS] SQL Syntax Check detected error: {err}")
    else:
        print("[FAIL] SQL Syntax Check failed to detect error")

def test_data_iq():
    print("\nTesting DataIQ...")
    rows = [{"a": 1, "b": None}, {"a": 1, "b": None}] # 100% duplicate, 50% null
    res = analyze_result(rows)
    if res["confidence_score"] < 1.0:
        print(f"[PASS] DataIQ detected issues: {res['anomalies']}")
    else:
        print("[FAIL] DataIQ failed to detect issues")

def test_prompt_loader():
    print("\nTesting PromptLoader...")
    path = os.path.join("src", "prompts", "small_schema", "query_planner.yaml")
    vars = {"USER_QUERY": "test", "SCHEMA": "test", "DIALECT_INSTRUCTIONS": "test", 
            "PREVIOUS_ACTION_PLAN": "test", "FEEDBACK_ON_PREVIOUS_ACTION_PLAN": "test", 
            "RESOLVED_ELEMENTS": "[]", "EXTERNAL_KNOWLEDGE": "test", "REFERENCE_DATE": "test",
            "INTENT": "test"}
    try:
        msgs = PromptLoader.load(path, variables=vars)
        if len(msgs) > 0:
            print("[PASS] PromptLoader")
        else:
            print("[FAIL] PromptLoader returned empty messages")
    except Exception as e:
        print(f"[FAIL] PromptLoader: {e}")

async def main():
    await test_pydantic_models()
    test_sql_validator()
    test_data_iq()
    test_prompt_loader()
    print("\nDiagnostic complete.")

if __name__ == "__main__":
    asyncio.run(main())
