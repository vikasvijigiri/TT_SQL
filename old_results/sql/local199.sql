WITH rental_counts AS (
    SELECT s.store_id,
           CAST(strftime('%Y', r.rental_date) AS INTEGER) AS year,
           CAST(strftime('%m', r.rental_date) AS INTEGER) AS month,
           COUNT(*) AS total_rentals
    FROM rental r
    JOIN staff s ON r.staff_id = s.staff_id
    GROUP BY s.store_id, year, month
),
max_counts AS (
    SELECT store_id, MAX(total_rentals) AS max_total
    FROM rental_counts
    GROUP BY store_id
)
SELECT rc.store_id, rc.year, rc.month, rc.total_rentals
FROM rental_counts rc
JOIN max_counts mc ON rc.store_id = mc.store_id AND rc.total_rentals = mc.max_total
ORDER BY rc.store_id;