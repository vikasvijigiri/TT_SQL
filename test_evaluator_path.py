import os
import sys

# Mimic the logic in src/tt_sql/core/evaluator.py
# We assume this script is running from project root, but we want to simulate
# the logic as if it were inside src/tt_sql/core/evaluator.py

# Let's define the path where evaluator.py lives
mock_evaluator_path = os.path.abspath("src/tt_sql/core/evaluator.py")
print(f"Mock Evaluator Path: {mock_evaluator_path}")

current_dir = os.path.dirname(mock_evaluator_path)
print(f"current_dir (src/tt_sql/core): {current_dir}")

tt_sql_dir = os.path.dirname(current_dir) # src/tt_sql
print(f"tt_sql_dir: {tt_sql_dir}")

src_dir = os.path.dirname(tt_sql_dir)     # src
print(f"src_dir: {src_dir}")

project_root = os.path.dirname(src_dir)   # Project Root
print(f"project_root: {project_root}")

eval_script = os.path.join(tt_sql_dir, "utils", "collect_failures.py")
print(f"eval_script: {eval_script}")

expected_root = os.getcwd()
print(f"Expected Root: {expected_root}")

if project_root == expected_root:
    print("SUCCESS: Project root matches.")
else:
    print("FAILURE: Project root mismatch.")

if os.path.exists(eval_script):
    print("SUCCESS: Eval script found.")
else:
    print("FAILURE: Eval script NOT found.")
