WITH filtered_business AS (
    SELECT business_id
    FROM "business"
    WHERE lower(description) LIKE '%indianapolis%'
      AND lower(description) LIKE '%indiana%'
)
SELECT AVG(r.rating)::DOUBLE AS average_rating
FROM "review" r
JOIN filtered_business b
  ON REPLACE(r.business_ref, 'businessref_', '') = REPLACE(b.business_id, 'businessid_', '');