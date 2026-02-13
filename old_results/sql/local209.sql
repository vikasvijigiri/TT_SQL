WITH order_counts AS (
    SELECT s.store_id, s.store_name, COUNT(o.order_id) AS total_orders
    FROM orders o
    JOIN stores s ON o.store_id = s.store_id
    GROUP BY s.store_id, s.store_name
),
max_store AS (
    SELECT store_id, store_name, total_orders
    FROM order_counts
    ORDER BY total_orders DESC
    LIMIT 1
),
 delivered_counts AS (
    SELECT ms.store_id, COUNT(DISTINCT o.order_id) AS delivered_orders
    FROM max_store ms
    JOIN orders o ON o.store_id = ms.store_id
    JOIN deliveries d ON d.delivery_order_id = o.order_id
    WHERE d.delivery_status = 'DELIVERED'
    GROUP BY ms.store_id
)
SELECT ms.store_id,
       ms.store_name,
       CAST(dc.delivered_orders AS REAL) / ms.total_orders AS delivered_ratio
FROM max_store ms
LEFT JOIN delivered_counts dc ON dc.store_id = ms.store_id;