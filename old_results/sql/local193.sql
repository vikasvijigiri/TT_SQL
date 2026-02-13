WITH first_purchase AS (
    SELECT customer_id, MIN(payment_date) AS first_date
    FROM payment
    GROUP BY customer_id
),
customer_sales AS (
    SELECT p.customer_id,
           SUM(p.amount) AS total_sales,
           SUM(CASE WHEN p.payment_date <= datetime(fp.first_date, '+7 days') THEN p.amount ELSE 0 END) AS sales_7d,
           SUM(CASE WHEN p.payment_date <= datetime(fp.first_date, '+30 days') THEN p.amount ELSE 0 END) AS sales_30d
    FROM payment p
    JOIN first_purchase fp ON p.customer_id = fp.customer_id
    GROUP BY p.customer_id
    HAVING total_sales > 0
),
percentages AS (
    SELECT (CAST(sales_7d AS REAL) / total_sales) * 100.0 AS pct_7d,
           (CAST(sales_30d AS REAL) / total_sales) * 100.0 AS pct_30d,
           total_sales
    FROM customer_sales
)
SELECT AVG(pct_7d) AS avg_pct_7d,
       AVG(pct_30d) AS avg_pct_30d,
       AVG(total_sales) AS avg_ltv
FROM percentages;