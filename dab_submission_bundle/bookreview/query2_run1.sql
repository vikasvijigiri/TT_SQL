WITH book_avg AS (
    SELECT
        "books_info"."book_id",
        "books_info"."title",
        "books_info"."author",
        AVG("review"."rating") AS avg_rating
    FROM "books_info"
    JOIN "review"
        ON REPLACE("books_info"."book_id", 'bookid_', '') = REPLACE("review"."purchase_id", 'purchaseid_', '')
    WHERE "books_info"."categories" LIKE '%Literature & Fiction%'
      AND "books_info"."details" LIKE '%English%'
    GROUP BY "books_info"."book_id", "books_info"."title", "books_info"."author"
    HAVING AVG("review"."rating") = 5.0
)
SELECT "title", "author"
FROM book_avg;