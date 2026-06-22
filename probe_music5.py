import duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'
conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH IF NOT EXISTS '{base}/tracks.db' AS tdb (TYPE sqlite)")

# The normalized title approach from db_description hint
result = conn.execute("""
    WITH normalized AS (
        SELECT
            regexp_replace(
                regexp_replace(t.title, '^[0-9]+-', ''),
                ' [-|].+$', ''
            ) AS base_title,
            s.revenue_usd
        FROM main.sales s
        JOIN tdb.tracks t ON s.track_id = t.track_id
    )
    SELECT base_title, SUM(revenue_usd) AS total_rev
    FROM normalized
    GROUP BY base_title
    ORDER BY total_rev DESC
    LIMIT 5
""").fetchdf()
print("Top 5 normalized titles:")
print(result)

conn.close()
