SELECT COUNT(DISTINCT b.business_id) AS business_count
FROM "business_db"."business" b
JOIN "review" r
  ON REPLACE(b.business_id, 'businessid_', 'businessref_') = r.business_ref
WHERE regexp_extract(r."date", '(19[0-9]{2}|20[0-9]{2})', 1) = '2018'
  AND (
        json_extract_string(b.attributes, '$.BikeParking') = 'True'
        OR json_extract_string(b.attributes, '$.BusinessParking') LIKE '%True%'
      );