import duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'
conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH IF NOT EXISTS '{base}/tracks.db' AS tdb (TYPE sqlite)")

# Plain query without normalization
print("=== Plain GROUP BY title (no normalization) ===")
result = conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) AS total_rev
    FROM main.sales s
    JOIN tdb.tracks t ON s.track_id = t.track_id
    WHERE t.title IS NOT NULL AND t.title != ''
    GROUP BY t.title
    ORDER BY total_rev DESC
    LIMIT 10
""").fetchdf()
print(result.to_string())

# What about joining with NO title filter?
print("\n=== ALL titles (including NULL) ===")
result2 = conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) AS total_rev
    FROM main.sales s
    JOIN tdb.tracks t ON s.track_id = t.track_id
    GROUP BY t.title
    ORDER BY total_rev DESC
    LIMIT 5
""").fetchdf()
print(result2.to_string())
conn.close()
