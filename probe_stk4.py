import duckdb, sqlite3

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'

# Connect to primary DuckDB
conn = duckdb.connect(f'{base}/stocktrade_query.db')
print("Primary opened")

# Attach stockinfo
si_path = f"{base}/stockinfo_query.db".replace("\\", "/")
conn.execute("INSTALL sqlite; LOAD sqlite;")
conn.execute(f"ATTACH IF NOT EXISTS '{si_path}' AS stockinfo_db (TYPE sqlite);")
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "stockinfo" AS SELECT * FROM stockinfo_db.stockinfo;')
print("Stockinfo ready")

# Check if all_stocktrade_query exists (it's a view from the schema linker)
try:
    cnt = conn.execute("SELECT COUNT(*) FROM all_stocktrade_query LIMIT 1").fetchone()[0]
    print(f"all_stocktrade_query exists: {cnt}")
except Exception as e:
    print(f"all_stocktrade_query NOT found: {e}")
    # Need to create it - let's look at the tables available
    tabs = conn.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='main' AND table_name NOT LIKE 'duckdb_%' AND table_name NOT LIKE 'sqlite_%'
        ORDER BY table_name LIMIT 20
    """).fetchall()
    print("First 20 tables:", [t[0] for t in tabs])

# Check _entity_name values for NYSE symbols
print("\n=== _entity_name sample for NYSE stocks ===")
try:
    # Find some known NYSE tickers in all_stocktrade_query
    result = conn.execute("""
        SELECT DISTINCT _entity_name FROM all_stocktrade_query
        WHERE _entity_name IN ('AEFC', 'AIN', 'AIV', 'AIZP', 'AJRD', 'JNJ', 'AAPL', 'IBM')
        LIMIT 20
    """).fetchdf()
    print("Found NYSE tickers:", result['_entity_name'].tolist())
except Exception as e:
    print(f"Error: {e}")

# Test 2017 rows exist for stockinfo symbols
print("\n=== 2017 coverage for NYSE non-ETF stocks ===")
try:
    result2 = conn.execute("""
        WITH nyse_nonETF AS (
            SELECT Symbol FROM stockinfo
            WHERE "Listing Exchange" = 'N' AND "ETF" = 'N'
        )
        SELECT COUNT(DISTINCT st._entity_name) as tickers_with_2017_data
        FROM all_stocktrade_query st
        JOIN nyse_nonETF si ON st._entity_name = si."Symbol"
        WHERE st."Date" >= '2017-01-01' AND st."Date" < '2018-01-01'
    """).fetchone()[0]
    print(f"NYSE non-ETF tickers with 2017 data: {result2}")
except Exception as e:
    print(f"Error: {e}")

# Try the full query
print("\n=== Full q4 query ===")
try:
    result3 = conn.execute("""
        WITH updown AS (
            SELECT _entity_name,
                   SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) as up_days,
                   SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) as down_days
            FROM all_stocktrade_query
            WHERE "Date" >= '2017-01-01' AND "Date" < '2018-01-01'
            GROUP BY _entity_name
        )
        SELECT si."Company Description"
        FROM updown ud
        JOIN stockinfo si ON ud._entity_name = si."Symbol"
        WHERE si."Listing Exchange" = 'N' AND si."ETF" = 'N'
        AND ud.up_days > ud.down_days
        ORDER BY ud.up_days DESC
        LIMIT 5
    """).fetchdf()
    print("Top 5:", result3)
except Exception as e:
    print(f"Full query error: {e}")

conn.close()
