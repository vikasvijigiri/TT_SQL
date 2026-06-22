import re

log_path = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\c1126b6c-f42e-42f8-8284-e65e517de103\.system_generated\tasks\task-756.log"

with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's search for "DAB Evaluation:" or "Evaluation:" or similar
print("=== EVALUATION RESULTS ===")
eval_matches = re.finditer(r".*Evaluation:.*", content, re.IGNORECASE)
for m in eval_matches:
    print(m.group(0))

print("\n=== SYSTEM ERRORS / EXCEPTIONS ===")
err_matches = re.finditer(r".*exception.*|.*error.*", content, re.IGNORECASE)
count = 0
for m in err_matches:
    line = m.group(0)
    # Filter out common logging of non-critical items if needed
    if any(k in line for k in ["Orchestrator", "Error", "failed", "Evaluation", "pre-flight"]):
        print(line)
        count += 1
        if count >= 30:
            break
