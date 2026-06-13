WITH "wifi_businesses" AS (
  SELECT
    REPLACE(b."business_id", 'businessid_', '') AS biz_id_stripped,
    b."business_id",
    regexp_extract(b."description", ', ([A-Z]{2})[,\s\.]', 1) AS state
  FROM "business" b
  WHERE b."attributes" LIKE '%WiFi%'
    AND regexp_extract(b."description", ', ([A-Z]{2})[,\s\.]', 1) != ''
),
"reviews" AS (
  SELECT
    REPLACE(r."business_ref", 'businessref_', '') AS biz_ref_stripped,
    r."rating"
  FROM "review" r
)
SELECT
  wb.state,
  COUNT(DISTINCT wb.business_id) AS biz_cnt,
  AVG(r.rating) AS avg_rating
FROM "wifi_businesses" wb
JOIN "reviews" r
  ON r.biz_ref_stripped = wb.biz_id_stripped
GROUP BY wb.state
ORDER BY biz_cnt DESC
LIMIT 1;