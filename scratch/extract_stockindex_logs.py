log_path = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\c1126b6c-f42e-42f8-8284-e65e517de103\.system_generated\tasks\task-756.log"

with open(log_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

in_stockindex = False
for idx, line in enumerate(lines):
    if "STOCKINDEX" in line or "stockindex" in line:
        # Let's print lines around stockindex runs
        # Specifically, we want the logs of STOCKINDEX / QUERY 1, 2, or 3
        pass

# Let's write a simple search that prints lines containing "stockindex" and 10 lines after
for idx, line in enumerate(lines):
    if "DAB: STOCKINDEX / QUERY 1" in line:
        print(f"=== STOCKINDEX Q1 START (Line {idx+1}) ===")
        for i in range(idx, min(len(lines), idx + 200)):
            print(lines[i].strip())
        break
