WITH "joined" AS (
  SELECT
    REGEXP_EXTRACT(b."description", ', ([A-Z]{2})[\,\s\.]', 1) AS state,
    r."rating"::DOUBLE AS rating
  FROM "business_db"."business" b
  JOIN "review" r
    ON REPLACE(b."business_id", 'businessid_', '') = REPLACE(r."business_ref", 'businessref_', '')
  WHERE REGEXP_EXTRACT(b."description", ', ([A-Z]{2})[\,\s\.]', 1) IS NOT NULL
    AND REGEXP_EXTRACT(b."description", ', ([A-Z]{2})[\,\s\.]', 1) != ''
)
SELECT
  state,
  COUNT(*) AS review_count,
  AVG(rating) AS avg_rating
FROM "joined"
GROUP BY state
ORDER BY review_count DESC
LIMIT 1;