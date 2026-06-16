WITH reviews_2018 AS (
  SELECT DISTINCT r.business_ref
  FROM "review" r
  WHERE regexp_extract(r."date", '(19[0-9]{2}|20[0-9]{2})', 1) = '2018'
), qualified_businesses AS (
  SELECT b.business_id
  FROM "business" b
  JOIN reviews_2018 r ON REPLACE(b.business_id, 'businessid_', 'businessref_') = r.business_ref
  WHERE COALESCE(json_extract_string(b.attributes, '$.BikeParking'), '') = 'True'
     OR COALESCE(json_extract_string(b.attributes, '$.BusinessParking.lot'), '') = 'True'
     OR COALESCE(json_extract_string(b.attributes, '$.BusinessParking.garage'), '') = 'True'
     OR COALESCE(json_extract_string(b.attributes, '$.BusinessParking.street'), '') = 'True'
     OR COALESCE(json_extract_string(b.attributes, '$.BusinessParking.validated'), '') = 'True'
     OR COALESCE(json_extract_string(b.attributes, '$.BusinessParking.valet'), '') = 'True'
)
SELECT COUNT(DISTINCT business_id) AS business_count
FROM qualified_businesses;