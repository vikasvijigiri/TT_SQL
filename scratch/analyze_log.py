import re

log_path = r"C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\resources\logs\run_and_audit_failed_heavy.log"
with open(log_path, "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

print(f"Total lines in log: {len(lines)}")
token_lines = [l for l in lines if "Tokens:" in l]
print(f"Total token lines found: {len(token_lines)}")
for tl in token_lines[:15]:
    print(tl.strip())
