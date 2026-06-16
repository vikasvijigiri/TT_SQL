WITH filtered_tracks AS (
    SELECT DISTINCT "track_id"
    FROM sqlite_scan('C:/Users/VikasVijigiri/Documents/DataAgentBench/query_music_brainz_20k/query_dataset/tracks.db', 'tracks')
    WHERE lower("artist") = lower('Beyoncé')
      AND (
          lower("title") LIKE '%get me bodied%'
          OR lower(REPLACE("title", ' ', '')) LIKE '%getmebodied%'
      )
)
SELECT COALESCE(SUM(s."revenue_usd"), 0.0) AS "total_revenue_usd"
FROM "sales" s
JOIN filtered_tracks ft ON s."track_id" = ft."track_id"
WHERE s."store" = 'Apple Music'
  AND s."country" = 'Canada';