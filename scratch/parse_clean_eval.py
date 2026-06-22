import re

log_path = r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2\parallel_run_clean.log"

with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()

print("=== AGENT ANSWERS AND EVALUATIONS ===")
for idx, line in enumerate(lines):
    if "AGENT ANSWER:" in line or "DAB Evaluation:" in line:
        print(f"Line {idx+1}: {line}")
        # Print a few preceding/succeeding lines to get context
        start = max(0, idx - 2)
        end = min(len(lines), idx + 4)
        for i in range(start, end):
            if i != idx:
                print(f"  {i+1}: {lines[i]}")
        print("-" * 60)
