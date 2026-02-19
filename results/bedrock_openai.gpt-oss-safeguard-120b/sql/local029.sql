SELECT
    c.customer_unique_id,
    c.customer_city AS city,
    c.customer_state AS state,
    COUNT(DISTINCT o.order_id) AS delivered_order_count,
    AVG(op.payment_value) AS average_payment_value
FROM olist_orders o
JOIN olist_customers c ON o.customer_id = c.customer_id
JOIN olist_order_payments op ON o.order_id = op.order_id
WHERE LOWER(o.order_status) = 'delivered'
GROUP BY c.customer_unique_id, c.customer_city, c.customer_state
ORDER BY delivered_order_count DESC
LIMIT 3