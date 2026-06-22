import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'

# Check stockinfo structure
conn = duckdb.connect(f'{base}/stockinfo_query.db', read_only=True)
print("=== STOCKINFO tables ===")
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print('Tables:', tables['table_name'].tolist())
for tbl in tables['table_name'].tolist():
    cols = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{tbl}'").fetchdf()
    print(f"  {tbl}: {cols['column_name'].tolist()}")

print("\n=== Sample stockinfo rows (NYSE stocks) ===")
sample = conn.execute("""
    SELECT "Symbol", "Listing Exchange", "ETF", "Company Description"
    FROM stockinfo
    WHERE "Listing Exchange" = 'N' AND "ETF" = 'N'
    LIMIT 5
""").fetchdf()
print(sample.to_string())

# Count NYSE non-ETF stocks in stockinfo
count = conn.execute("SELECT COUNT(*) FROM stockinfo WHERE \"Listing Exchange\"='N' AND \"ETF\"='N'").fetchone()
print(f"\nNYSE non-ETF stocks in stockinfo: {count[0]}")
conn.close()

# Check stocktrade structure
conn2 = duckdb.connect(f'{base}/stocktrade_query.db', read_only=True)
print("\n=== STOCKTRADE tables (first 10) ===")
tables2 = conn2.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print(f'Total tables: {len(tables2)}')
print('First 10:', tables2['table_name'].tolist()[:10])

# Sample one stock table
first_tbl = tables2['table_name'].iloc[0]
cols2 = conn2.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{first_tbl}'").fetchdf()
print(f"\n{first_tbl} columns: {cols2['column_name'].tolist()}")
sample2 = conn2.execute(f"SELECT * FROM \"{first_tbl}\" LIMIT 3").fetchdf()
print(sample2.head())

# Try the full query: top 5 NYSE non-ETF stocks with more up days than down days in 2017
print("\n=== Full query attempt ===")
# First let's look at NYSE non-ETF symbols in stockinfo
nyse_symbols = conn2.execute("""
    ATTACH ? AS si_db (TYPE duckdb);
""", [f'{base}/stockinfo_query.db'])
conn2.execute(f"ATTACH '{base}/stockinfo_query.db' AS si_db")

nyse = conn2.execute("""
    SELECT si_db.stockinfo.Symbol
    FROM si_db.stockinfo
    WHERE si_db.stockinfo."Listing Exchange" = 'N'
      AND si_db.stockinfo."ETF" = 'N'
""").fetchdf()
print(f"NYSE non-ETF symbols: {len(nyse)}")
print(nyse.head(10))

conn2.close()
