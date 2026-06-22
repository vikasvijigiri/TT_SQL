import pathlib

results_root = pathlib.Path("backend/agent/agent/results")
matches = list(results_root.glob("**/query*.md"))
print(f"Found {len(matches)} query markdown files:")
for m in matches[:15]:
    print(f"  {m}")

matches_log = list(results_root.glob("**/query*.log"))
print(f"Found {len(matches_log)} query log files:")
for m in matches_log[:15]:
    print(f"  {m}")
