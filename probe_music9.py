import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'
conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH IF NOT EXISTS '{base}/tracks.db' AS tdb (TYPE sqlite)")

# Check if "base_title" literally exists
res = conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) as rev
    FROM main.sales s JOIN tdb.tracks t ON s.track_id = t.track_id
    WHERE t.title = 'base_title'
    GROUP BY t.title
""").fetchall()
print(f"Tracks with title='base_title': {res}")

# Run the EXACT SQL the pipeline generated
res2 = conn.execute("""
SELECT base_title FROM (
  SELECT regexp_replace(regexp_replace(t."title", '^[0-9]+-', ''), ' [-|].+$', '') AS base_title,
         SUM(s."revenue_usd") AS total_rev
  FROM "sales" s
  JOIN "tracks" t ON s."track_id" = t."track_id"
  GROUP BY base_title
  ORDER BY total_rev DESC
  LIMIT 1
) AS top
""").fetchdf()
print(f"Pipeline SQL result: {res2.to_dict()}")

# What is the track with NULL title and highest revenue that becomes "base_title"?
res3 = conn.execute("""
    SELECT regexp_replace(regexp_replace(t.title, '^[0-9]+-', ''), ' [-|].+$', '') AS norm_title,
           SUM(s.revenue_usd) as rev
    FROM main.sales s JOIN tdb.tracks t ON s.track_id = t.track_id
    GROUP BY norm_title
    ORDER BY rev DESC
    LIMIT 5
""").fetchdf()
print(f"\nTop 5 by norm_title:")
for _, row in res3.iterrows():
    print(f"  {repr(row['norm_title'])}: {row['rev']:.2f}")

conn.close()
