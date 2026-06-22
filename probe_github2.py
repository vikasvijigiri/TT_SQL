import sqlite3, duckdb

# Check repo_metadata.db structure
base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_GITHUB_REPOS\query_dataset'
conn = sqlite3.connect(f'{base}/repo_metadata.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tables:", tables)

for t in tables[:5]:
    cursor.execute(f"PRAGMA table_info('{t}')")
    cols = cursor.fetchall()
    print(f"\n{t}: {[c[1] for c in cols]}")
    cursor.execute(f"SELECT * FROM '{t}' LIMIT 3")
    print(cursor.fetchall())

# Find Java repos with stars
print("\n=== Top 5 Java repos by stars ===")
try:
    cursor.execute("""
        SELECT r.full_name, r.stargazers_count, l.language
        FROM repos r
        JOIN languages l ON r.full_name = l.repo_name
        WHERE l.language = 'Java'
        ORDER BY r.stargazers_count DESC
        LIMIT 5
    """)
    print(cursor.fetchall())
except Exception as e:
    print(f"Error: {e}")
    # Try with repos table columns
    cursor.execute("PRAGMA table_info('repos')")
    print("repos cols:", [c[1] for c in cursor.fetchall()])
    cursor.execute("PRAGMA table_info('languages')")
    print("languages cols:", [c[1] for c in cursor.fetchall()])

conn.close()

# Also check the q4 question and answer
import os
qdir = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_GITHUB_REPOS\query4'
for f in os.listdir(qdir):
    if f.endswith('.json') or f.endswith('.txt') or f.endswith('.csv'):
        print(f"\n=== {f} ===")
        try:
            with open(os.path.join(qdir, f), encoding='utf-8', errors='replace') as fh:
                print(fh.read()[:500])
        except:
            pass
