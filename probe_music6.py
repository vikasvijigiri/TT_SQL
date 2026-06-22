import duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'
conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH IF NOT EXISTS '{base}/tracks.db' AS tdb (TYPE sqlite)")

# Check NULL/empty titles
null_rev = conn.execute("""
    SELECT COUNT(*) as cnt, SUM(s.revenue_usd) as rev
    FROM main.sales s
    JOIN tdb.tracks t ON s.track_id = t.track_id
    WHERE t.title IS NULL OR t.title = '' OR t.title = '[untitled]'
""").fetchone()
print(f"NULL/empty/untitled tracks revenue: {null_rev}")

# Filtered normalized approach
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
        WHERE t.title IS NOT NULL
          AND t.title != ''
          AND t.title != '[untitled]'
    )
    SELECT base_title, SUM(revenue_usd) AS total_rev
    FROM normalized
    WHERE base_title IS NOT NULL AND base_title != ''
    GROUP BY base_title
    ORDER BY total_rev DESC
    LIMIT 5
""").fetchdf()
print("\nTop 5 normalized titles (filtered):")
print(result)

# Check "Zo gaat" specifically
zo_result = conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) as rev, COUNT(*) as cnt
    FROM main.sales s
    JOIN tdb.tracks t ON s.track_id = t.track_id
    WHERE t.title LIKE '%Zo gaat%'
    GROUP BY t.title
    ORDER BY rev DESC
""").fetchdf()
print("\nZo gaat variants:")
print(zo_result)

conn.close()
