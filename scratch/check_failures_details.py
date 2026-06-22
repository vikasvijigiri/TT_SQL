import re

log_path = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\c1126b6c-f42e-42f8-8284-e65e517de103\.system_generated\tasks\task-756.log"

with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's search for "AGENT ANSWER:" or "Evaluation:" for each query
queries = [
    "github_repos_q1",
    "github_repos_q2",
    "github_repos_q3",
    "github_repos_q4",
    "music_brainz_20k_q1",
    "stockindex_q1",
    "stockindex_q2",
    "stockindex_q3"
]

print("=== FAILURE INVESTIGATION ===")
for q in queries:
    print(f"\n--- {q} ---")
    # Find section in log for this query
    # Typically it has "DAB: GITHUB_REPOS / QUERY 1" etc.
    # Let's search for the evaluation log lines and the AGENT ANSWER line
    # We can do this by regex or by parsing
    # Let's find matches of "AGENT ANSWER:" or "DAB Evaluation:" within the logs
    
# Let's write a parser that extracts the block of text from "AGENT ANSWER" and "DAB Evaluation" in the log
# Let's search for occurrences of "DAB Evaluation:" and "AGENT ANSWER:"
lines = content.splitlines()
for idx, line in enumerate(lines):
    if "AGENT ANSWER:" in line or "DAB Evaluation:" in line or "Final Result Preview" in line:
        # Print a few lines before and after
        start = max(0, idx - 4)
        end = min(len(lines), idx + 6)
        print(f"L{idx+1}:")
        for i in range(start, end):
            print(f"  {lines[i]}")
        print("." * 40)
