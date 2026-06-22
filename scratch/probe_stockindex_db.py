import duckdb

db_path = r"C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockindex\query_dataset\indextrade_query.db"
conn = duckdb.connect(db_path)

print("=== TABLES IN DB ===")
tables = conn.execute("SHOW TABLES").fetchall()
for t in tables:
    print(t)
    # Print schema
    schema = conn.execute(f"PRAGMA table_info('{t[0]}')").fetchall()
    print("Schema:")
    for col in schema:
        print(f"  {col}")
    
    # Print sample rows
    print("Sample rows:")
    rows = conn.execute(f"SELECT * FROM '{t[0]}' LIMIT 3").fetchall()
    for r in rows:
        print(f"  {r}")
    print("-" * 50)

conn.close()
