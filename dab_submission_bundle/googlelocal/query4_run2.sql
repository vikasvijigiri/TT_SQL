WITH "filtered_reviews" AS (
  SELECT "r"."gmap_id"
  FROM "review" AS "r"
  WHERE "r"."rating" = 5
    AND CAST(regexp_extract("r"."time", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) = 2019
    AND "r"."gmap_id" IS NOT NULL
)
SELECT "bd"."name" AS "business_name",
       COUNT(*) AS "high_rating_review_count"
FROM "filtered_reviews" AS "fr"
JOIN "business_description" AS "bd"
  ON "fr"."gmap_id" = "bd"."gmap_id"
WHERE "bd"."name" IS NOT NULL AND TRIM("bd"."name") != ''
GROUP BY "bd"."name"
ORDER BY "high_rating_review_count" DESC, "bd"."name" ASC
LIMIT 3;