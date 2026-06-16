WITH ind_businesses AS (
    SELECT "business_id"
    FROM "business_db"."business"
    WHERE lower("description") LIKE '%indianapolis%'
      AND lower("description") LIKE '%indiana%'
), cleaned_ids AS (
    SELECT REPLACE("business_id", 'businessid_', '') AS clean_id
    FROM ind_businesses
)
SELECT AVG(r."rating")::DOUBLE AS "average_rating"
FROM "review" r
JOIN cleaned_ids c
  ON REPLACE(r."business_ref", 'businessref_', '') = c.clean_id;