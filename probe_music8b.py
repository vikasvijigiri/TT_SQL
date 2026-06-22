import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'
conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH IF NOT EXISTS '{base}/tracks.db' AS tdb (TYPE sqlite)")

# Aggressive filter
result = conn.execute("""
    WITH cleaned AS (
        SELECT t.title, s.revenue_usd
        FROM main.sales s JOIN tdb.tracks t ON s.track_id = t.track_id
        WHERE t.title IS NOT NULL
          AND length(t.title) > 3
          AND t.title NOT IN ('[untitled]','unknown','n.a.','[silence]','unk.','[vocal]','[spoken]')
          AND NOT regexp_matches(t.title, '^[0-9]+[-. ]*$')
    ),
    norm AS (
        SELECT
            regexp_replace(regexp_replace(title, '^[0-9]+-?\\s*', ''), '\\s[-|–]\\s.+$', '') AS bt,
            revenue_usd
        FROM cleaned
        WHERE title IS NOT NULL
    )
    SELECT bt, SUM(revenue_usd) AS rev
    FROM norm
    WHERE bt IS NOT NULL AND length(bt) > 3
    GROUP BY bt
    ORDER BY rev DESC
    LIMIT 10
""").fetchdf()
for _, row in result.iterrows():
    print(f"  {row['bt']!r}: {row['rev']:.2f}")

conn.close()
