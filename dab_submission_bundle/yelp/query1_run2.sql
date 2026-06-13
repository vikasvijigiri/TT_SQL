SELECT AVG(r."rating")::DOUBLE AS "average_rating"
FROM "review" r
JOIN "business_db"."business" b
  ON REPLACE(b."business_id", 'businessid_', '') = REPLACE(r."business_ref", 'businessref_', '')
WHERE lower(b."description") LIKE '%indianapolis%'
  AND lower(b."description") LIKE '%indiana%';