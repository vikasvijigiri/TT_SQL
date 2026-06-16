WITH "parsed_reviews" AS (
  SELECT
    REPLACE("review"."business_ref", 'businessref_', '') AS biz_key,
    "review"."rating",
    TRY_STRPTIME("review"."date", '%B %d, %Y at %I:%M %p') AS review_ts
  FROM "review"
),
"date_filtered" AS (
  SELECT biz_key, rating
  FROM "parsed_reviews"
  WHERE review_ts IS NOT NULL
    AND review_ts >= TIMESTAMP '2016-01-01'
    AND review_ts < TIMESTAMP '2016-07-01'
),
"biz_stats" AS (
  SELECT
    biz_key,
    COUNT(*) AS review_cnt,
    AVG(rating)::DOUBLE AS avg_rating
  FROM "date_filtered"
  GROUP BY biz_key
  HAVING COUNT(*) >= 5
)
SELECT
  b."name" AS business_name,
  bs.avg_rating,
  COALESCE(
    NULLIF(regexp_extract(b."description", 'menu featuring (.+?)(?:, (?:perfect|ideal|making|convenient)|[.] )', 1), ''),
    NULLIF(regexp_extract(b."description", 'services\s*(?:in|including) ([^.]+)\.', 1), ''),
    NULLIF(regexp_extract(b."description", '(?:mix of|ranging from|services in|array of (?:dishes |options )?in) ([^.]+)\.', 1), ''),
    b."description"
  ) AS category
FROM "biz_stats" bs
JOIN "business" b
  ON REPLACE(b."business_id", 'businessid_', '') = bs.biz_key
ORDER BY bs.avg_rating DESC
LIMIT 1;