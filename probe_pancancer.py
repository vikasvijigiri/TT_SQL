import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_pancancer_atlas\query_dataset'
conn = duckdb.connect(f'{base}/pancancer_query.db', read_only=True)

# Check tables
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print('Tables:', tables['table_name'].tolist())

# Check each table's columns
for tbl in tables['table_name'].tolist():
    cols = conn.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{tbl}'").fetchdf()
    print(f"\n{tbl} columns:")
    print(cols.to_string())

conn.close()
