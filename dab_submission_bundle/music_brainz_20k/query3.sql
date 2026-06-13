WITH "cleaned_tracks" AS (
    SELECT
        t."track_id",
        t."title",
        LOWER(TRIM(t."title")) AS "norm_title"
    FROM "tracks" t
    WHERE t."title" IS NOT NULL
      AND TRIM(t."title") != ''
      AND LOWER(TRIM(t."title")) NOT IN ('unknown','n.a.','[untitled]','unk.','unk')
      AND NOT REGEXP_MATCHES(t."title", '^\d{1,3}[-_]?$')
),
"track_revenue" AS (
    SELECT
        ct."norm_title",
        MIN(ct."title") AS "track_title",
        SUM(s."revenue_usd") AS "total_revenue_usd"
    FROM "cleaned_tracks" ct
    JOIN "sales" s ON ct."track_id" = s."track_id"
    GROUP BY ct."norm_title"
)
SELECT "track_title", "total_revenue_usd"
FROM "track_revenue"
ORDER BY "total_revenue_usd" DESC
LIMIT 1;