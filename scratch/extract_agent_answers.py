import re

log_path = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\c1126b6c-f42e-42f8-8284-e65e517de103\.system_generated\tasks\task-756.log"

with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()

print("=== AGENT ANSWERS AND EVALUATIONS ===")
for idx, line in enumerate(lines):
    if "AGENT ANSWER:" in line:
        print(f"Line {idx+1}: {line}")
        # Print next 5 lines
        for j in range(1, 6):
            if idx + j < len(lines):
                print(f"  + {lines[idx+j]}")
        print("-" * 50)
