WITH "extracted" AS (
  SELECT
    CAST(regexp_extract(b."details", '\b(19\d{2}|20\d{2})\b', 1) AS INTEGER) AS pub_year,
    ((CAST(regexp_extract(b."details", '\b(19\d{2}|20\d{2})\b', 1) AS INTEGER) / 10) * 10) AS decade,
    r."rating" AS rating,
    b."book_id" AS book_id
  FROM "review" r
  JOIN "books_info" b
    ON REPLACE(r."purchase_id", 'purchaseid_', '') = REPLACE(b."book_id", 'bookid_', '')
  WHERE r."rating" IS NOT NULL
    AND b."details" IS NOT NULL
    AND CAST(regexp_extract(b."details", '\b(19\d{2}|20\d{2})\b', 1) AS INTEGER) IS NOT NULL
),
"decade_stats" AS (
  SELECT
    decade,
    AVG(rating) AS avg_rating,
    COUNT(DISTINCT book_id) AS distinct_books
  FROM "extracted"
  GROUP BY decade
  HAVING COUNT(DISTINCT book_id) >= 10
),
"ranked" AS (
  SELECT
    decade,
    avg_rating,
    ROW_NUMBER() OVER (ORDER BY avg_rating DESC) AS rn
  FROM "decade_stats"
)
SELECT decade
FROM "ranked"
WHERE rn = 1;