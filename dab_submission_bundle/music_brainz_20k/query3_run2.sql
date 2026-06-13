WITH "cleaned_tracks" AS (
    SELECT "track_id", "title"
    FROM "tracks_db"."tracks"
    WHERE "title" IS NOT NULL
      AND TRIM("title") <> ''
      AND LOWER(TRIM("title")) NOT IN ('unknown','n.a.','[untitled]','unk','unk.')
),
"track_revenue" AS (
    SELECT "track_id", SUM("revenue_usd") AS "total_revenue_usd"
    FROM "sales"
    GROUP BY "track_id"
)
SELECT ct."title" AS "track_title",
       tr."total_revenue_usd"
FROM "track_revenue" tr
JOIN "cleaned_tracks" ct ON ct."track_id" = tr."track_id"
ORDER BY tr."total_revenue_usd" DESC
LIMIT 1;