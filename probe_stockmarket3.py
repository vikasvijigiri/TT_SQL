import duckdb, sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'
stocktrade_path = f'{base}/stocktrade_query.db'
stockinfo_path = f'{base}/stockinfo_query.db'

# Connect to stocktrade (DuckDB primary), attach stockinfo (SQLite)
conn = duckdb.connect(stocktrade_path, read_only=False)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{stockinfo_path}' AS si_db (TYPE sqlite)")
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "stockinfo" AS SELECT * FROM "si_db"."stockinfo";')

# Verify NYSE stocks
nyse = conn.execute("""
    SELECT COUNT(*) as cnt FROM stockinfo
    WHERE "Listing Exchange" = 'N' AND "ETF" = 'N'
""").fetchone()
print(f"NYSE non-ETF stocks: {nyse[0]}")

# List all tables and see what the unified view should be called
tables = conn.execute("SHOW TABLES").fetchdf()
print(f"Total tables: {len(tables)}")
print(f"First 5 tables: {tables['name'].tolist()[:5]}")

# Check if stocktrade tables have Date column (for 2017 filter)
sample = conn.execute('SELECT * FROM "AEFC" WHERE "Date" LIKE \'2017%\' LIMIT 3').fetchdf()
print(f"\nAEFC 2017 sample:\n{sample.to_string()}")

# Now compute up_days/down_days for all NYSE non-ETF stocks in 2017
# But we need to UNION ALL 234 NYSE stocks first
# Let's get the list of NYSE non-ETF symbols that exist in stocktrade
nyse_symbols = conn.execute("""
    SELECT si."Symbol"
    FROM stockinfo si
    WHERE si."Listing Exchange" = 'N' AND si."ETF" = 'N'
""").fetchdf()
print(f"\nNYSE non-ETF symbols sample: {nyse_symbols['Symbol'].tolist()[:10]}")

# Check which of those symbols exist as tables in stocktrade
# First let's see the table names
table_names = set(tables['name'].tolist())
nyse_in_trade = [s for s in nyse_symbols['Symbol'].tolist() if s in table_names]
print(f"\nNYSE non-ETF symbols in stocktrade DB: {len(nyse_in_trade)}")
print(f"Sample: {nyse_in_trade[:10]}")

# Build a UNION ALL for all NYSE non-ETF stocks in stocktrade
# (This is what all_stocktrade_query does for ALL stocks, but we need the join)
parts = [f"SELECT '{s}' AS _entity_name, * FROM \"{s}\" WHERE \"Date\" >= '2017-01-01' AND \"Date\" < '2018-01-01'"
         for s in nyse_in_trade[:20]]  # test with first 20
test_sql = "SELECT _entity_name, SUM(CASE WHEN \"Close\" > \"Open\" THEN 1 ELSE 0 END) AS up_days, SUM(CASE WHEN \"Close\" < \"Open\" THEN 1 ELSE 0 END) AS down_days FROM (" + " UNION ALL ".join(parts) + ") GROUP BY _entity_name ORDER BY up_days DESC LIMIT 10"
result = conn.execute(test_sql).fetchdf()
print(f"\nTest up/down for first 20 NYSE stocks in 2017:\n{result.to_string()}")

conn.close()
