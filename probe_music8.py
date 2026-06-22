import duckdb, re

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'
conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH IF NOT EXISTS '{base}/tracks.db' AS tdb (TYPE sqlite)")

# Filter placeholder titles and normalize
result = conn.execute("""
    WITH cleaned AS (
        SELECT
            t.title,
            s.revenue_usd
        FROM main.sales s
        JOIN tdb.tracks t ON s.track_id = t.track_id
        WHERE t.title IS NOT NULL
          AND length(t.title) > 2
          AND t.title NOT IN ('[untitled]', 'unknown', 'n.a.', '[silence]', 'unk.', '1', '2', '3')
          AND NOT regexp_matches(t.title, '^[0-9]+[-.]?$')
    ),
    normalized AS (
        SELECT
            regexp_replace(
                regexp_replace(title, '^[0-9]+-?\\s*', ''),
                '\\s[-|–]\\s.+$', ''
            ) AS base_title,
            revenue_usd
        FROM cleaned
        WHERE title IS NOT NULL
    )
    SELECT base_title, SUM(revenue_usd) AS total_rev
    FROM normalized
    WHERE base_title IS NOT NULL AND length(base_title) > 3
    GROUP BY base_title
    ORDER BY total_rev DESC
    LIMIT 15
""").fetchdf()
print("Top 15 filtered+normalized:")
print(result.to_string())

conn.close()
