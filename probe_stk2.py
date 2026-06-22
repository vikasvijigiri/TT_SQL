import duckdb, sqlite3

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'

# Test direct approach: attach stockinfo to stocktrade DuckDB
print("=== Test stockinfo attachment ===")
try:
    conn = duckdb.connect(f'{base}/stocktrade_query.db', read_only=True)
    print("Primary DuckDB opened")

    # Load sqlite extension
    try:
        conn.execute("INSTALL sqlite; LOAD sqlite;")
        print("SQLite extension loaded")
    except Exception as e:
        print(f"SQLite ext error: {e}")

    # Attach stockinfo
    si_path = f"{base}/stockinfo_query.db".replace("\\", "/")
    try:
        conn.execute(f"ATTACH IF NOT EXISTS '{si_path}' AS stockinfo_db (TYPE sqlite);")
        print("Stockinfo attached!")
        tabs = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='stockinfo_db'").fetchdf()
        print("Stockinfo tables:", tabs['table_name'].tolist())
    except Exception as e:
        print(f"Attachment failed: {e}")

    conn.close()
except Exception as e:
    print(f"Primary open error: {e}")

# Test stockinfo directly
print("\n=== Stockinfo content ===")
conn2 = sqlite3.connect(f'{base}/stockinfo_query.db')
cursor = conn2.cursor()
cursor.execute("SELECT COUNT(*) FROM stockinfo")
print("Row count:", cursor.fetchone())
# Get sample NYSE non-ETF stocks
cursor.execute("""
    SELECT Symbol, "Listing Exchange", ETF, "Company Description"
    FROM stockinfo
    WHERE "Listing Exchange" = 'N' AND ETF = 'N'
    LIMIT 5
""")
nyse_stocks = cursor.fetchall()
print("NYSE non-ETF stocks (sample):", nyse_stocks)
conn2.close()

# Now try the full question query
print("\n=== Test full stockmarket query ===")
try:
    conn3 = duckdb.connect(f'{base}/stocktrade_query.db', read_only=True)
    conn3.execute("INSTALL sqlite; LOAD sqlite;")
    si_path = f"{base}/stockinfo_query.db".replace("\\", "/")
    conn3.execute(f"ATTACH '{si_path}' AS stockinfo_db (TYPE sqlite);")

    # Create stockinfo as a view
    conn3.execute("CREATE TEMP VIEW stockinfo AS SELECT * FROM stockinfo_db.stockinfo;")
    print("Stockinfo view created")

    # Test simple query
    result = conn3.execute("""
        SELECT si."Symbol", si."Company Description"
        FROM stockinfo si
        WHERE si."Listing Exchange" = 'N' AND si."ETF" = 'N'
        LIMIT 5
    """).fetchdf()
    print("NYSE non-ETF from stockinfo:", result)

    # Test join with all_stocktrade_query for 2017 up days
    result2 = conn3.execute("""
        WITH updown AS (
            SELECT _entity_name,
                   SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) as up_days,
                   SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) as down_days
            FROM all_stocktrade_query
            WHERE "Date" >= '2017-01-01' AND "Date" < '2018-01-01'
            GROUP BY _entity_name
        ),
        qualified AS (
            SELECT si."Company Description", si."Symbol", ud.up_days, ud.down_days
            FROM updown ud
            JOIN stockinfo si ON ud._entity_name = si."Symbol"
            WHERE si."Listing Exchange" = 'N' AND si."ETF" = 'N'
            AND ud.up_days > ud.down_days
        )
        SELECT "Company Description"
        FROM qualified
        ORDER BY up_days DESC
        LIMIT 5
    """).fetchdf()
    print("Top 5 results:", result2)
    conn3.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback; traceback.print_exc()
