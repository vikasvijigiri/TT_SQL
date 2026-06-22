import sqlite3
import os

db_path = r"C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockindex\query_dataset\indexInfo_query.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("=== TABLES IN indexInfo_query ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()
for t in tables:
    print(t[0])
    cur.execute(f"PRAGMA table_info('{t[0]}');")
    schema = cur.fetchall()
    for col in schema:
        print(f"  {col}")
    
    cur.execute(f"SELECT * FROM '{t[0]}' LIMIT 5;")
    rows = cur.fetchall()
    print("Sample rows:")
    for r in rows:
        print(f"  {r}")
    print("-" * 50)

conn.close()
