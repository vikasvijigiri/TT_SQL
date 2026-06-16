WITH "track_revenue" AS (
    SELECT s."track_id", SUM(s."revenue_usd") AS "total_revenue_usd"
    FROM "sales" s
    GROUP BY s."track_id"
),
"song_revenue" AS (
    SELECT t."title" AS "track_title",
           t."artist",
           t."album",
           SUM(tr."total_revenue_usd") AS "total_revenue_usd"
    FROM "tracks_db"."tracks" t
    JOIN "track_revenue" tr ON t."track_id" = tr."track_id"
    GROUP BY t."title", t."artist", t."album"
)
SELECT "track_title" AS "title",
       "artist",
       "album",
       "total_revenue_usd"
FROM "song_revenue"
ORDER BY "total_revenue_usd" DESC
LIMIT 1;