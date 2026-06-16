WITH "joined" AS (
  SELECT
    r."rating",
    b."book_id",
    CAST(regexp_extract(b."details", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) AS pub_year
  FROM "books_info" b
  JOIN "review" r
    ON REPLACE(b."book_id", 'bookid_', '') = REPLACE(r."purchase_id", 'purchaseid_', '')
  WHERE r."rating" IS NOT NULL
    AND b."details" IS NOT NULL
    AND CAST(regexp_extract(b."details", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) IS NOT NULL
),
"decade_agg" AS (
  SELECT
    CAST((pub_year / 10) * 10 AS INTEGER) AS decade,
    AVG(rating) AS avg_rating,
    COUNT(DISTINCT book_id) AS distinct_book_cnt
  FROM "joined"
  GROUP BY decade
  HAVING COUNT(DISTINCT book_id) >= 10
),
"ranked" AS (
  SELECT
    decade,
    avg_rating,
    ROW_NUMBER() OVER (ORDER BY avg_rating DESC) AS rn
  FROM "decade_agg"
)
SELECT decade
FROM "ranked"
WHERE rn = 1;