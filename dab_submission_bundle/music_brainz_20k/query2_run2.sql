WITH filtered_tracks AS (
    SELECT DISTINCT "track_id"
    FROM "tracks_db"."tracks"
    WHERE LOWER("artist") = LOWER('Brucqe Maginnis')
      AND LOWER("title") LIKE LOWER('%Street Hype%')
      AND "track_id" IS NOT NULL
)
SELECT s."store",
       COALESCE(SUM(s."revenue_usd"), 0.0) AS "total_revenue_usd"
FROM "sales" AS s
JOIN filtered_tracks ft ON s."track_id" = ft."track_id"
GROUP BY s."store"
ORDER BY "total_revenue_usd" DESC
LIMIT 1;