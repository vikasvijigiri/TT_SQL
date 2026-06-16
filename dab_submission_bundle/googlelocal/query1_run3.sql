WITH "filtered_businesses" AS (
    SELECT "gmap_id", "name"
    FROM "business_description"
    WHERE LOWER("description") LIKE '%los angeles, ca%'
),
"business_ratings" AS (
    SELECT fb."name" AS "business_name",
           AVG(r."rating") AS "avg_rating",
           COUNT(r."rating") AS "review_count"
    FROM "filtered_businesses" fb
    JOIN "review" r ON r."gmap_id" = fb."gmap_id"
    GROUP BY fb."name"
)
SELECT "business_name", "avg_rating", "review_count"
FROM "business_ratings"
ORDER BY "avg_rating" DESC, "review_count" DESC
LIMIT 5;