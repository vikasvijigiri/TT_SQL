WITH monthly_totals AS (
    SELECT
        customer_id,
        strftime('%Y-%m', payment_date) AS year_month,
        SUM(amount) AS month_total
    FROM payment
    GROUP BY customer_id, year_month
),
monthly_changes AS (
    SELECT
        customer_id,
        month_total,
        month_total - LAG(month_total) OVER (PARTITION BY customer_id ORDER BY year_month) AS change
    FROM monthly_totals
),
avg_changes AS (
    SELECT
        customer_id,
        AVG(change) AS avg_monthly_change
    FROM monthly_changes
    WHERE change IS NOT NULL
    GROUP BY customer_id
)
SELECT
    c.first_name || ' ' || c.last_name AS full_name
FROM avg_changes ac
JOIN customer c ON c.customer_id = ac.customer_id
ORDER BY ac.avg_monthly_change DESC
LIMIT 1;