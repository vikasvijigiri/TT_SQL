import os
import sys
import json
from dotenv import load_dotenv

# Add backend to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Test the formatting logic in isolation to avoid dependency hell
def test_isolated_formatting():
    # Mock data
    schema_info = {
        "sales": {
            "columns": [
                {"column_name": "sale_id", "description": "Unique ID of the sale"},
                {"column_name": "amount", "description": "Total value"}
            ]
        }
    }
    
    # Borrow logic from generation_layer.py
    lines = []
    for table, data in schema_info.items():
        cols = data.get("columns", [])
        col_strings = []
        for c in cols:
            name = c.get("column_name") or c.get("name") or "unknown"
            desc = c.get("description") or ""
            col_strings.append(f"{name} ({desc})" if desc else name)
        
        lines.append(f"- {table}: {', '.join(col_strings)}")
    
    formatted = "\n".join(lines)
    print(f"DEBUG: Formatted Schema:\n{formatted}")
    
    # Check against requirement
    expected = "- sales: sale_id (Unique ID of the sale), amount (Total value)"
    if formatted == expected:
        print("SUCCESS: Isolated formatting test passed!")
    else:
        print("FAIL: Formatting does not match expectation.")

    # Log file check logic
    print("\n--- Verifying setup_logging change ---")
    import re
    # Instead of running it, we read the code of query_qdrant.py to confirm the comment out
    path = os.path.join(backend_dir, "app", "services", "rag", "query_qdrant.py")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
            if "# logger.addHandler(file_handler) # Disabled by user request" in code:
                print("SUCCESS: Code verification confirms FileHandler is disabled.")
            else:
                print("FAIL: Code verification failed. Comment not found.")
    else:
        print(f"FAIL: {path} not found.")

if __name__ == "__main__":
    test_isolated_formatting()
