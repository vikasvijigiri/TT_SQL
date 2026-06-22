import duckdb

# Probe music_brainz
print("=== MUSIC_BRAINZ ===")
conn = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset\sales.duckdb', read_only=True)
print("Tables:", conn.execute("SHOW TABLES").fetchall())
print("\nSales schema:")
print(conn.execute("DESCRIBE sales").fetchdf())
print("\nTop 5 revenue songs (sum revenue_usd):")
print(conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) as rev
    FROM sales s JOIN tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title ORDER BY rev DESC LIMIT 5
""").fetchdf())
print("\nTop 5 revenue songs (unit_price * quantity from invoiceline if exists):")
try:
    print(conn.execute("SELECT * FROM information_schema.tables WHERE table_name LIKE '%invoice%'").fetchdf())
except Exception as e:
    print(f"No invoiceline: {e}")
conn.close()

print("\n=== STOCKMARKET ===")
conn2 = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset\stocktrade_query.db', read_only=True)
print("Tables:", conn2.execute("SHOW TABLES").fetchall())
try:
    print("\nall_stocktrade_query sample:")
    print(conn2.execute("SELECT * FROM all_stocktrade_query LIMIT 3").fetchdf().columns.tolist())
except Exception as e:
    print(f"all_stocktrade_query error: {e}")
# Find non-ETF top 5 companies
try:
    tabs = conn2.execute("SHOW TABLES").fetchdf()
    print("\nTables list:", tabs['name'].tolist())
except Exception as e:
    print(f"Tables error: {e}")
conn2.close()

print("\n=== CRMARENAPRO - Field__c values ===")
conn3 = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset\sales_pipeline.duckdb', read_only=True)
print("Tables:", conn3.execute("SHOW TABLES").fetchall())
try:
    print("\nField__c DISTINCT values:")
    print(conn3.execute("SELECT DISTINCT \"Field__c\" FROM (SELECT * FROM information_schema.tables)").fetchdf())
except Exception as e:
    print(f"Field__c query error: {e}")
# Try all tables
try:
    tabs = conn3.execute("SHOW TABLES").fetchdf()
    for t in tabs['name'].tolist()[:5]:
        try:
            cols = conn3.execute(f'DESCRIBE "{t}"').fetchdf()
            field_col = [c for c in cols['column_name'].tolist() if 'field' in c.lower() or 'Field' in c]
            if field_col:
                print(f"\nTable {t}, columns with 'field': {field_col}")
                for fc in field_col[:2]:
                    vals = conn3.execute(f'SELECT DISTINCT "{fc}" FROM "{t}" LIMIT 15').fetchdf()
                    print(f"  {fc} values:", vals[fc].tolist())
        except Exception as e2:
            print(f"Error on {t}: {e2}")
except Exception as e:
    print(f"Tables error: {e}")
conn3.close()
