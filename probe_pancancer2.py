import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_PANCANCER_ATLAS\query_dataset'

# Check clinical DB
print("=== CLINICAL DB ===")
conn = duckdb.connect(f'{base}/pancancer_clinical.db', read_only=True)
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print('Tables:', tables['table_name'].tolist())
for tbl in tables['table_name'].tolist():
    cols = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{tbl}'").fetchdf()
    print(f"  {tbl}: {cols['column_name'].tolist()[:15]}")
    # Sample
    sample = conn.execute(f"SELECT * FROM {tbl} LIMIT 2").fetchdf()
    print(f"    Sample row: {dict(sample.iloc[0]) if len(sample) > 0 else 'empty'}")
conn.close()

print("\n=== MOLECULAR DB ===")
conn2 = duckdb.connect(f'{base}/pancancer_molecular.db', read_only=True)
tables2 = conn2.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print('Tables:', tables2['table_name'].tolist())
for tbl in tables2['table_name'].tolist():
    cols = conn2.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{tbl}'").fetchdf()
    print(f"  {tbl}: {cols['column_name'].tolist()[:15]}")
    # Sample
    sample = conn2.execute(f"SELECT * FROM {tbl} LIMIT 2").fetchdf()
    print(f"    Sample row: {dict(sample.iloc[0]) if len(sample) > 0 else 'empty'}")
conn2.close()
