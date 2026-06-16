WITH "filtered_reviews" AS (
  SELECT r."gmap_id",
         bd."name" AS business_name
  FROM "review" r
  JOIN "business_description" bd ON r."gmap_id" = bd."gmap_id"
  WHERE r."rating" >= 5
    AND CAST(regexp_extract(r."time", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) = 2019
)
SELECT business_name,
       COUNT(*) AS high_rating_review_count
FROM "filtered_reviews"
GROUP BY business_name
ORDER BY high_rating_review_count DESC, business_name ASC
LIMIT 3;