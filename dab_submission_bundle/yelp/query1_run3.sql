WITH ind_businesses AS (
  SELECT "business_id"
  FROM "business_db"."business"
  WHERE lower("description") LIKE '%indianapolis%'
    AND lower("description") LIKE '%indiana%'
)
SELECT AVG(r."rating")::DOUBLE AS "average_rating"
FROM ind_businesses b
JOIN "review" r
  ON REPLACE(b."business_id", 'businessid_', '') = REPLACE(r."business_ref", 'businessref_', '');