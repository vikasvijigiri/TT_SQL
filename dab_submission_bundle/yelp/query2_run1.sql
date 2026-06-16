WITH "business_state" AS (
  SELECT "business_id",
         REGEXP_EXTRACT("description", ', ([A-Z]{2})[,\s\.]', 1) AS state
  FROM "business_db"."business"
  WHERE REGEXP_EXTRACT("description", ', ([A-Z]{2})[,\s\.]', 1) != ''
), "joined" AS (
  SELECT bs.state,
         r.rating
  FROM "business_state" bs
  JOIN "review" r
    ON REPLACE(bs.business_id, 'businessid_', '') = REPLACE(r.business_ref, 'businessref_', '')
)
SELECT state,
       COUNT(*) AS review_count,
       AVG(rating) AS avg_rating
FROM "joined"
GROUP BY state
ORDER BY review_count DESC
LIMIT 1;