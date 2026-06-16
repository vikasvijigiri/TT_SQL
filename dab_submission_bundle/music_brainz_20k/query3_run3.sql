WITH track_rev AS (
    SELECT s."track_id", SUM(s."revenue_usd") AS total_revenue_usd
    FROM "sales" s
    GROUP BY s."track_id"
)
SELECT t."title" AS track_title,
       tr.total_revenue_usd
FROM track_rev tr
JOIN "tracks" t ON t."track_id" = tr."track_id"
ORDER BY tr.total_revenue_usd DESC
LIMIT 1;