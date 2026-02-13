WITH delivered_orders AS (
    SELECT order_id, customer_id
    FROM olist_orders
    WHERE order_status = 'delivered'
),
order_items_with_orders AS (
    SELECT oi.order_id, oi.seller_id, oi.price, oi.freight_value, c.customer_unique_id
    FROM olist_order_items oi
    JOIN delivered_orders do ON oi.order_id = do.order_id
    JOIN olist_customers c ON do.customer_id = c.customer_id
),
customer_unique_counts AS (
    SELECT seller_id, COUNT(DISTINCT customer_unique_id) AS unique_customers
    FROM order_items_with_orders
    GROUP BY seller_id
),
profit_per_seller AS (
    SELECT seller_id, SUM(price - freight_value) AS total_profit
    FROM order_items_with_orders
    GROUP BY seller_id
),
distinct_orders_per_seller AS (
    SELECT seller_id, COUNT(DISTINCT order_id) AS distinct_orders
    FROM order_items_with_orders
    GROUP BY seller_id
),
five_star_reviews AS (
    SELECT oi.seller_id, COUNT(*) AS five_star_count
    FROM order_items_with_orders oi
    JOIN olist_order_reviews r ON oi.order_id = r.order_id
    WHERE r.review_score = 5
    GROUP BY oi.seller_id
)
SELECT seller_id, unique_customers AS value, 'Highest number of distinct customer unique IDs' AS achievement
FROM customer_unique_counts
ORDER BY unique_customers DESC
LIMIT 1
UNION ALL
SELECT seller_id, total_profit AS value, 'Highest profit' AS achievement
FROM profit_per_seller
ORDER BY total_profit DESC
LIMIT 1
UNION ALL
SELECT seller_id, distinct_orders AS value, 'Highest number of distinct orders' AS achievement
FROM distinct_orders_per_seller
ORDER BY distinct_orders DESC
LIMIT 1
UNION ALL
SELECT seller_id, five_star_count AS value, 'Most 5-star ratings' AS achievement
FROM five_star_reviews
ORDER BY five_star_count DESC
LIMIT 1;