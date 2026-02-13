WITH daily_counts AS (
    SELECT d.driver_id,
           o.order_created_year,
           o.order_created_month,
           o.order_created_day,
           COUNT(*) AS deliveries_per_day
    FROM deliveries d
    JOIN orders o ON d.delivery_order_id = o.delivery_order_id
    GROUP BY d.driver_id, o.order_created_year, o.order_created_month, o.order_created_day
)
SELECT dc.driver_id,
       AVG(dc.deliveries_per_day) AS avg_daily_deliveries
FROM daily_counts dc
GROUP BY dc.driver_id
ORDER BY avg_daily_deliveries DESC
LIMIT 5;