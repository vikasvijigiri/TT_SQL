import sqlite3, duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_DEPS_DEV_V1\query_dataset'

print("=== project_query.db (DuckDB) ===")
conn = duckdb.connect(f'{base}/project_query.db', read_only=True)
tabs = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print("Tables:", tabs['table_name'].tolist())
for t in tabs['table_name'].tolist():
    cols = conn.execute(f'DESCRIBE "{t}"').fetchdf()
    print(f"\n{t}: {cols['column_name'].tolist()}")
    print(conn.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchdf())
conn.close()

print("\n=== package_query.db (SQLite) - sample ===")
conn2 = sqlite3.connect(f'{base}/package_query.db')
cursor = conn2.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tables:", tables)
for t in tables[:3]:
    cursor.execute(f"PRAGMA table_info('{t}')")
    cols = [c[1] for c in cursor.fetchall()]
    print(f"\n{t}: {cols}")
    cursor.execute(f"SELECT * FROM '{t}' LIMIT 2")
    print(cursor.fetchall())
conn2.close()
