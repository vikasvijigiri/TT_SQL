import duckdb, sys, sqlite3
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'
conn = duckdb.connect(f'{base}/yelp_user.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/business.db' AS biz (TYPE sqlite)")

# Check review columns
r = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='review'").fetchdf()
print(f"review columns:\n{r.to_string()}")

# Sample reviews
rs = conn.execute("SELECT * FROM review LIMIT 2").fetchdf()
print(f"\nreview sample:\n{rs.columns.tolist()}")
for c in rs.columns:
    print(f"  {c}: {rs[c].iloc[0]}")

conn.close()
