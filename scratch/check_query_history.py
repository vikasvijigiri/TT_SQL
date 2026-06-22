import sqlite3
import sys

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

db_path = r"C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\results\evaluations\nquire.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

targets = [
    ("github_repos", "1"),
    ("github_repos", "2"),
    ("github_repos", "3"),
    ("music_brainz_20k", "1"),
    ("stockindex", "3")
]

for ds, qid in targets:
    print(f"\n==================================================")
    print(f"HISTORY FOR {ds} Q{qid}")
    print(f"==================================================")
    cur.execute(
        "SELECT run_id, username, passed, reason, elapsed_s, agent_answer_snippet, timestamp "
        "FROM evaluations WHERE dataset = ? AND query_id = ? "
        "ORDER BY timestamp DESC",
        (ds, qid)
    )
    rows = cur.fetchall()
    print(f"Total historical runs found: {len(rows)}")
    for r in rows:
        reason_str = str(r['reason']).encode('ascii', errors='replace').decode('ascii')
        ans_str = str(r['agent_answer_snippet']).encode('ascii', errors='replace').decode('ascii')
        print(f"[{r['timestamp']}] run_id: {r['run_id']} | user: {r['username']} | passed: {r['passed']} | answer: {ans_str} | reason: {reason_str}")

conn.close()
