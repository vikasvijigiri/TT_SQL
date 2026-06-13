WITH parsed_reviews AS (
  SELECT
    REPLACE(business_ref, 'businessref_', 'businessid_') AS business_id,
    rating::DOUBLE AS rating,
    COALESCE(
      TRY_STRPTIME(date, '%B %d, %Y at %I:%M %p'),
      TRY_STRPTIME(date, '%d %b %Y, %H:%M'),
      TRY_STRPTIME(date, '%Y-%m-%d %H:%M:%S'),
      TRY_STRPTIME(date, '%Y-%m-%d')
    )::DATE AS review_date
  FROM "review"
),
filtered_reviews AS (
  SELECT *
  FROM parsed_reviews
  WHERE review_date BETWEEN DATE '2016-01-01' AND DATE '2016-06-30'
),
agg AS (
  SELECT business_id,
         COUNT(*) AS review_cnt,
         AVG(rating) AS avg_rating
  FROM filtered_reviews
  GROUP BY business_id
  HAVING COUNT(*) >= 5
),
ranked AS (
  SELECT business_id,
         avg_rating,
         review_cnt,
         ROW_NUMBER() OVER (ORDER BY avg_rating DESC) AS rn
  FROM agg
)
SELECT b.name AS business_name,
       COALESCE(
         NULLIF(regexp_extract(b.description, '(?i)category: ([A-Za-z, /&()''-]+)', 1), ''),
         NULLIF(regexp_extract(b.description, '(?i)categories? of ([A-Za-z, /&()''-]+)', 1), ''),
         NULLIF(regexp_extract(b.description, '(?i)type: ([A-Za-z, /&()''-]+)', 1), ''),
         NULLIF(regexp_extract(b.description, '(?i)\b([A-Za-z]+) business\b', 1), '')
       ) AS category,
       r.avg_rating,
       r.review_cnt
FROM ranked r
JOIN "business_db"."business" b ON b.business_id = r.business_id
WHERE r.rn = 1;
