WITH parking_businesses AS (
  SELECT b.business_id
  FROM "business_db"."business" b
  WHERE json_extract_string(b.attributes, '$.BusinessParking') IS NOT NULL
     OR json_extract_string(b.attributes, '$.BikeParking') IS NOT NULL
),
reviews_2018 AS (
  SELECT DISTINCT r.business_ref
  FROM "review" r
  WHERE regexp_extract(r."date", '(19[0-9]{2}|20[0-9]{2})', 1) = '2018'
)
SELECT COUNT(DISTINCT pb.business_id) AS business_count
FROM parking_businesses pb
JOIN reviews_2018 r201
  ON REPLACE(pb.business_id, 'businessid_', 'businessref_') = r201.business_ref;