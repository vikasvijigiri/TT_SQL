WITH city_aggregates AS (
    SELECT c.customer_city AS city,
           SUM(p.payment_value) AS total_payment,
           COUNT(DISTINCT o.order_id) AS delivered_order_count
    FROM olist_orders o
    JOIN olist_customers c ON o.customer_id = c.customer_id
    JOIN olist_order_payments p ON o.order_id = p.order_id
    WHERE LOWER(o.order_status) = 'delivered'
    GROUP BY c.customer_city
    ORDER BY total_payment ASC
    LIMIT 5
)
SELECT city,
       total_payment,
       delivered_order_count,
       (SELECT AVG(total_payment) FROM city_aggregates) AS avg_total_payment,
       (SELECT AVG(delivered_order_count) FROM city_aggregates) AS avg_delivered_order_count
FROM city_aggregates
ORDER BY total_payment ASC;