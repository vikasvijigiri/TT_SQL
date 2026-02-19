WITH monthly_counts AS (
    SELECT CAST(strftime('%Y', order_delivered_customer_date) AS INTEGER) AS year,
           CAST(strftime('%m', order_delivered_customer_date) AS INTEGER) AS month,
           COUNT(*) AS monthly_delivered_orders
    FROM olist_orders
    WHERE order_delivered_customer_date IS NOT NULL
      AND strftime('%Y', order_delivered_customer_date) IN ('2016','2017','2018')
    GROUP BY year, month
),
annual_totals AS (
    SELECT year, SUM(monthly_delivered_orders) AS annual_total
    FROM monthly_counts
    GROUP BY year
),
lowest_year AS (
    SELECT year
    FROM annual_totals
    ORDER BY annual_total ASC
    LIMIT 1
)
SELECT mc.year,
       mc.month,
       mc.monthly_delivered_orders AS highest_monthly_delivered_orders
FROM monthly_counts mc
JOIN lowest_year ly ON mc.year = ly.year
ORDER BY mc.monthly_delivered_orders DESC
LIMIT 1;