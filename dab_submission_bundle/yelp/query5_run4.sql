WITH "wifi_businesses" AS (
  SELECT
    b."business_id",
    regexp_extract(b."description", ', ([A-Z]{2})[\,\s\.]', 1) AS state
  FROM "business" b
  WHERE b."attributes" LIKE '%WiFi%'
), "state_agg" AS (
  SELECT
    wb.state,
    COUNT(DISTINCT wb.business_id) AS biz_cnt,
    AVG(r.rating) AS avg_rating
  FROM "wifi_businesses" wb
  JOIN "review" r
    ON REPLACE(wb.business_id, 'businessid_', '') = REPLACE(r.business_ref, 'businessref_', '')
  WHERE wb.state IS NOT NULL AND wb.state != ''
  GROUP BY wb.state
)
SELECT state, biz_cnt, avg_rating
FROM "state_agg"
ORDER BY biz_cnt DESC
LIMIT 1;