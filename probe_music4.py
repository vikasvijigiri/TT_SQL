import duckdb, sqlite3, re

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'

# Must use DuckDB + attach SQLite
conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute(f"ATTACH '{base}/tracks.db' AS tdb (READ_ONLY)")

# Strip compilation suffixes to get base title
print("=== Normalized title aggregation ===")
# Try stripping everything after ' - ' (artist prefix approach)
df = conn.execute("""
    WITH normalized AS (
        SELECT
            regexp_replace(regexp_replace(t.title,
                '^[0-9]+-', ''),  -- strip leading "NNN-" numbering
                ' [-–|].+$', ''   -- strip " - Artist" or " | subtitle" suffix
            ) as base_title,
            s.revenue_usd
        FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    )
    SELECT base_title, SUM(revenue_usd) as rev
    FROM normalized
    GROUP BY base_title
    ORDER BY rev DESC LIMIT 10
""").fetchdf()
print(df)

# Try just stripping after ' (' (subtitle in parens)
print("\n=== Strip parens approach ===")
df2 = conn.execute("""
    WITH normalized AS (
        SELECT
            regexp_replace(t.title, ' \\(.*$', '') as base_title,
            s.revenue_usd
        FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    )
    SELECT base_title, SUM(revenue_usd) as rev
    FROM normalized
    GROUP BY base_title
    ORDER BY rev DESC LIMIT 10
""").fetchdf()
print(df2)

# Find exactly what key "Zo gaat" uses
print("\n=== All Zo gaat track IDs ===")
df3 = conn.execute("""
    SELECT t.track_id, t.title, t.source_id, t.source_track_id, SUM(s.revenue_usd) as rev
    FROM tdb.tracks t LEFT JOIN main.sales s ON t.track_id=s.track_id
    WHERE t.title LIKE '%Zo gaat%'
    GROUP BY t.track_id, t.title, t.source_id, t.source_track_id
    ORDER BY rev DESC NULLS LAST
""").fetchdf()
print(df3)

conn.close()
