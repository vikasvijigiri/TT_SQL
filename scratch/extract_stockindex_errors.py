log_path = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\c1126b6c-f42e-42f8-8284-e65e517de103\.system_generated\tasks\task-756.log"

with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's search for "indexInfo_query" or "index_info"
lines = content.splitlines()
for idx, line in enumerate(lines):
    if "index_info" in line.lower() or "indexinfo" in line.lower() or "indextrade" in line.lower():
        print(f"L{idx+1}: {line}")
