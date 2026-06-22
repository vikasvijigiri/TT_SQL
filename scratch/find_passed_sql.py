import sqlite3
import pathlib
import sys

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
    cur.execute(
        "SELECT id, run_id, username, passed, reason, elapsed_s, agent_answer_snippet, timestamp, run_suffix "
        "FROM evaluations WHERE dataset = ? AND query_id = ? AND passed = 1 "
        "ORDER BY timestamp DESC",
        (ds, qid)
    )
    rows = cur.fetchall()
    print(f"\nTarget: {ds} q{qid} - Passed runs found: {len(rows)}")
    for r in rows:
        reason_str = str(r['reason']).encode('ascii', errors='replace').decode('ascii')
        ans_str = str(r['agent_answer_snippet']).encode('ascii', errors='replace').decode('ascii')
        print(f"  [{r['timestamp']}] run_id: {r['run_id']} | user: {r['username']} | suffix: {r['run_suffix']} | answer: {ans_str} | reason: {reason_str}")
        
        user_safe = r['username'].lower()
        run_sfx = r['run_suffix']
        
        possibilities = []
        if r['run_id'] == 'failed_heavy_audit':
            possibilities.append(
                pathlib.Path(f"C:/Users/VikasVijigiri/Documents/TT_SQL_V2/backend/agent/agent/results/evaluations/users/{user_safe}/dab/_archive/failed_heavy_audit/{ds}/query{qid}{run_sfx}.sql")
            )
        elif r['run_id'] == 'live':
            possibilities.append(
                pathlib.Path(f"C:/Users/VikasVijigiri/Documents/TT_SQL_V2/backend/agent/agent/results/evaluations/users/{user_safe}/dab/{ds}/query{qid}{run_sfx}.sql")
            )
        else:
            possibilities.append(
                pathlib.Path(f"C:/Users/VikasVijigiri/Documents/TT_SQL_V2/backend/agent/agent/results/evaluations/users/{user_safe}/dab/_archive/{r['run_id']}/{ds}/query{qid}{run_sfx}.sql")
            )
            possibilities.append(
                pathlib.Path(f"C:/Users/VikasVijigiri/Documents/TT_SQL_V2/backend/agent/agent/results/evaluations/{r['run_id']}/{ds}/query{qid}{run_sfx}.sql")
            )
            
        for path in possibilities:
            if path.exists():
                print(f"    SQL File: {path}")
                print("    " + path.read_text(encoding="utf-8").replace("\n", "\n    "))
                break
        else:
            print("    No SQL file found on disk.")

conn.close()
