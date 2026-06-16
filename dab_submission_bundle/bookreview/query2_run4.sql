WITH avg_ratings AS (
    SELECT
        b."title",
        b."author",
        b."book_id",
        b."categories",
        b."details",
        AVG(CAST(r."rating" AS REAL)) AS avg_rating
    FROM "review" r
    JOIN "books_info" b
        ON r."title" = b."title"
    WHERE LOWER(b."categories") LIKE '%literature & fiction%'
      AND LOWER(b."details") LIKE '%english%'
    GROUP BY b."title", b."author", b."book_id", b."categories", b."details"
    HAVING AVG(CAST(r."rating" AS REAL)) = 5.0
)
SELECT * FROM avg_ratings;