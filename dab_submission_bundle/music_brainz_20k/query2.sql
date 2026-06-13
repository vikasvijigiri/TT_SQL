WITH matching_tracks AS (
    SELECT DISTINCT "track_id"
    FROM "tracks"
    WHERE lower("artist") LIKE '%brucqe maginnis%'
      AND lower("title") LIKE '%street hype%'
)
SELECT s."store",
       SUM(s."revenue_usd") AS total_revenue_usd
FROM "sales" s
JOIN matching_tracks mt ON s."track_id" = mt."track_id"
GROUP BY s."store"
ORDER BY total_revenue_usd DESC
LIMIT 1;