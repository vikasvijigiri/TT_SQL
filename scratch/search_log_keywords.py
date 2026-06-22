import pathlib

log_content = pathlib.Path("parallel_run_clean.log").read_text(encoding="utf-8")
keywords = [
    "cache", "latency", "security", "validator", "injection", "explain", "drift",
    "completeness", "sla", "determinism", "token", "rate_limiter", "rollback",
    "postgres", "mysql", "mssql", "snowflake", "oracle", "bigquery"
]
for kw in keywords:
    matches = []
    for line in log_content.splitlines():
        if kw in line.lower():
            matches.append(line)
    if matches:
        print(f"Keyword: '{kw}' has {len(matches)} matches. First 3:")
        for m in matches[:3]:
            print(f"  {m[:120]}")
