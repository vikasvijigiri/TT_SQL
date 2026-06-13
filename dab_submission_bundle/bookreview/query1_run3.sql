WITH "extracted" AS (
    SELECT
        bi."book_id",
        r."rating",
        CAST(regexp_extract(bi."details", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) AS pub_year
    FROM "books_info" bi
    JOIN "review" r
        ON bi."title" = r."title"
    WHERE r."rating" IS NOT NULL
      AND CAST(regexp_extract(bi."details", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) IS NOT NULL
),
"decades" AS (
    SELECT
        book_id,
        rating,
        CAST(pub_year / 10 AS INTEGER) * 10 AS decade
    FROM "extracted"
)
SELECT
    decade,
    AVG(rating) AS avg_rating
FROM "decades"
GROUP BY decade
HAVING COUNT(DISTINCT book_id) >= 10
ORDER BY avg_rating DESC
LIMIT 1;