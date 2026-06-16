WITH ind_businesses AS (
    SELECT REPLACE("business_id", 'businessid_', '') AS clean_id
    FROM "business_db"."business"
    WHERE lower("description") LIKE '%indianapolis%'
      AND lower("description") LIKE '%indiana%'
)
SELECT AVG(r."rating")::DOUBLE AS average_rating
FROM ind_businesses ib
JOIN "review" r
  ON ib.clean_id = REPLACE(r."business_ref", 'businessref_', '');