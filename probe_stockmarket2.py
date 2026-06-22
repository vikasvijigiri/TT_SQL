import duckdb, sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'
stocktrade_path = f'{base}/stocktrade_query.db'
stockinfo_path = f'{base}/stockinfo_query.db'

# Simulate what db_executor does
conn = duckdb.connect(stocktrade_path, read_only=False)  # need read-write for temp tables

# Auto-attach stockinfo
conn.execute(f"ATTACH '{stockinfo_path}' AS si_db (TYPE duckdb)")

# Create temp table for stockinfo
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "stockinfo" AS SELECT * FROM "si_db"."stockinfo";')

# Check if unified view exists (simulate creation)
print("Creating unified view all_stocktrade_query...")
all_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' UNION ALL SELECT name FROM sqlite_master WHERE type='view'").fetchdf()
print(f"(not running full union - too slow for 2753 tables)")

# Instead, just create a small test union to verify the approach
conn.execute("""
    CREATE OR REPLACE TEMPORARY VIEW "all_stocktrade_query_test" AS
    SELECT 'AAAU' AS _entity_name, * FROM "AAAU"
    UNION ALL
    SELECT 'AADR' AS _entity_name, * FROM "AADR"
    UNION ALL
    SELECT 'AAME' AS _entity_name, * FROM "AAME"
""")

# Test the query logic
print("=== Test query (small subset) ===")
test = conn.execute("""
    SELECT _entity_name,
           SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) as up_days,
           SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) as down_days
    FROM all_stocktrade_query_test
    WHERE Date >= '2017-01-01' AND Date < '2018-01-01'
    GROUP BY _entity_name
""").fetchdf()
print(test)

# Verify stockinfo is accessible
print("\n=== stockinfo temp table (NYSE, non-ETF sample) ===")
nyse = conn.execute("""
    SELECT Symbol, "Listing Exchange", "ETF", "Company Description"
    FROM stockinfo
    WHERE "Listing Exchange" = 'N' AND "ETF" = 'N'
    LIMIT 5
""").fetchdf()
print(nyse[['Symbol', 'ETF', 'Company Description']].to_string())

# Try the full query approach (using just AAAU,AADR,AAME as test)
print("\n=== Full query with stockinfo join ===")
result = conn.execute("""
    WITH nyse_non_etf AS (
        SELECT "Symbol", "Company Description" AS company_name
        FROM stockinfo
        WHERE "Listing Exchange" = 'N' AND "ETF" = 'N'
    ),
    updown AS (
        SELECT _entity_name AS symbol,
               SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) AS up_days,
               SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) AS down_days
        FROM all_stocktrade_query_test
        WHERE Date >= '2017-01-01' AND Date < '2018-01-01'
        GROUP BY _entity_name
    )
    SELECT n.company_name, u.up_days, u.down_days, (u.up_days - u.down_days) AS net_up
    FROM nyse_non_etf n
    JOIN updown u ON n."Symbol" = u.symbol
    WHERE u.up_days > u.down_days
    ORDER BY net_up DESC
    LIMIT 5
""").fetchdf()
print(result.to_string())
print("\n(Only 3 stocks tested - need full all_stocktrade_query for real answer)")

conn.close()
