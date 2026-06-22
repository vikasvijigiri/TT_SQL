import duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'

print("=== tracks.db schema ===")
conn = duckdb.connect(f'{base}/tracks.db', read_only=True)
tabs = conn.execute("SELECT table_schema, table_name FROM information_schema.tables ORDER BY 1,2").fetchdf()
print(tabs)
for t in tabs['table_name'].tolist():
    try:
        print(f"\n-- {t} --")
        print(conn.execute(f'DESCRIBE "{t}"').fetchdf()[['column_name','column_type']].to_string())
        print(conn.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchdf())
    except Exception as e:
        print(f"Error: {e}")
conn.close()

print("\n=== sales.duckdb + tracks.db attached === ")
conn2 = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
try:
    conn2.execute(f"ATTACH '{base}/tracks.db' AS tracks_db (READ_ONLY)")
    print("Attached! Tables in tracks_db:")
    print(conn2.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='tracks_db'").fetchdf())
    # Try the JOIN
    print("\nTop 5 revenue songs (cross-db join):")
    print(conn2.execute("""
        SELECT t.title, SUM(s.revenue_usd) as rev
        FROM sales s JOIN tracks_db.tracks t ON s.track_id=t.track_id
        GROUP BY t.track_id, t.title ORDER BY rev DESC LIMIT 5
    """).fetchdf())
except Exception as e:
    print(f"Attach failed: {e}")
conn2.close()

print("\n=== sales.duckdb direct sample ===")
conn3 = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
print(conn3.execute('SELECT * FROM sales LIMIT 5').fetchdf())
conn3.close()
