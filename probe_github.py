import duckdb

conn = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_GITHUB_REPOS\query_dataset\repo_artifacts.db', read_only=True)

tabs = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print("Tables:", tabs['table_name'].tolist())

for t in tabs['table_name'].tolist():
    print(f"\n-- {t} --")
    df = conn.execute(f'DESCRIBE "{t}"').fetchdf()
    print(df[['column_name','column_type']].to_string())
    print(conn.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchdf().to_string())

# Search for language column
for t in tabs['table_name'].tolist():
    df = conn.execute(f'DESCRIBE "{t}"').fetchdf()
    lang_cols = [c for c in df['column_name'].tolist() if 'lang' in c.lower()]
    repo_cols = [c for c in df['column_name'].tolist() if 'repo' in c.lower() or 'name' in c.lower() or 'star' in c.lower()]
    if lang_cols:
        print(f"\n{t} has language cols: {lang_cols}")
        for lc in lang_cols[:2]:
            print(conn.execute(f'SELECT DISTINCT "{lc}" FROM "{t}" LIMIT 20').fetchdf())
    if repo_cols:
        print(f"{t} repo/name/star cols: {repo_cols}")

# Try to find what query gives twbs/bootstrap
print("\n=== What query gives 'twbs/bootstrap'? ===")
try:
    print(conn.execute("SELECT * FROM files LIMIT 3").fetchdf())
    print("Files schema:")
    print(conn.execute("DESCRIBE files").fetchdf())
except Exception as e:
    print(f"files error: {e}")

conn.close()

# Also check stockinfo
print("\n=== STOCKINFO DB ===")
import sqlite3
try:
    conn2 = sqlite3.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset\stockinfo_query.db')
    cursor = conn2.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:", tables)
    for t in tables[:3]:
        tname = t[0]
        cursor.execute(f"PRAGMA table_info('{tname}')")
        cols = cursor.fetchall()
        print(f"\n{tname} columns:", [c[1] for c in cols])
        cursor.execute(f"SELECT * FROM '{tname}' LIMIT 3")
        print(cursor.fetchall())
    conn2.close()
except Exception as e:
    print(f"Stockinfo error: {e}")
