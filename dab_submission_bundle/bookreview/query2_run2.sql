WITH english_books AS (
    SELECT b.book_id, b.title, b.author, b.categories, b.details
    FROM "books_info" b
    WHERE b.categories LIKE '%Literature & Fiction%'
      AND b.details LIKE '%English%'
), review_agg AS (
    SELECT REPLACE(r.purchase_id, 'purchaseid_', '') AS book_key,
           AVG(CAST(r.rating AS REAL)) AS avg_rating,
           COUNT(*) AS review_cnt
    FROM "review" r
    GROUP BY REPLACE(r.purchase_id, 'purchaseid_', '')
    HAVING AVG(CAST(r.rating AS REAL)) = 5.0
)
SELECT eb.title,
       eb.author,
       eb.book_id,
       ra.avg_rating,
       ra.review_cnt
FROM english_books eb
JOIN review_agg ra
  ON REPLACE(eb.book_id, 'bookid_', '') = ra.book_key;
