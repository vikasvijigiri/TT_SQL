WITH total_per_customer AS (
    SELECT customer_id, SUM(amount) AS total_amount
    FROM payment
    GROUP BY customer_id
),
top_customers AS (
    SELECT customer_id
    FROM total_per_customer
    ORDER BY total_amount DESC
    LIMIT 10
),
monthly_totals AS (
    SELECT p.customer_id,
           strftime('%Y-%m', p.payment_date) AS year_month,
           SUM(p.amount) AS month_amount
    FROM payment p
    WHERE p.customer_id IN (SELECT customer_id FROM top_customers)
    GROUP BY p.customer_id, year_month
),
month_diff AS (
    SELECT mt.customer_id,
           mt.year_month,
           mt.month_amount,
           LEAD(mt.month_amount) OVER (PARTITION BY mt.customer_id ORDER BY mt.year_month) AS next_month_amount,
           ABS(mt.month_amount - LEAD(mt.month_amount) OVER (PARTITION BY mt.customer_id ORDER BY mt.year_month)) AS diff
    FROM monthly_totals mt
),
filtered_diff AS (
    SELECT *
    FROM month_diff
    WHERE next_month_amount IS NOT NULL
),
max_change AS (
    SELECT customer_id, year_month, diff
    FROM filtered_diff
    ORDER BY diff DESC
    LIMIT 1
)
SELECT c.customer_id,
       c.first_name,
       c.last_name,
       mc.year_month AS month,
       ROUND(mc.diff, 2) AS max_monthly_difference
FROM max_change mc
JOIN customer c ON mc.customer_id = c.customer_id;