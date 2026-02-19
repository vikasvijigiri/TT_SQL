WITH delivered_orders AS (
    SELECT order_id, customer_id
    FROM olist_orders
    WHERE LOWER(order_status) = 'delivered'
),
seller_metrics AS (
    SELECT oi.seller_id,
           COUNT(DISTINCT d.customer_id) AS distinct_customers,
           SUM(oi.price - oi.freight_value) AS total_profit,
           COUNT(DISTINCT oi.order_id) AS distinct_orders
    FROM delivered_orders d
    JOIN olist_order_items oi ON d.order_id = oi.order_id
    GROUP BY oi.seller_id
),
seller_five_star AS (
    SELECT oi.seller_id,
           COUNT(*) AS five_star_count
    FROM delivered_orders d
    JOIN olist_order_items oi ON d.order_id = oi.order_id
    JOIN olist_order_reviews r ON r.order_id = d.order_id
    WHERE r.review_score = 5
    GROUP BY oi.seller_id
),
combined AS (
    SELECT sm.seller_id,
           sm.distinct_customers,
           sm.total_profit,
           sm.distinct_orders,
           COALESCE(sf.five_star_count, 0) AS five_star_count
    FROM seller_metrics sm
    LEFT JOIN seller_five_star sf ON sm.seller_id = sf.seller_id
)
SELECT 'Highest number of distinct customers' AS achievement,
       seller_id,
       distinct_customers AS value
FROM combined
WHERE distinct_customers = (SELECT MAX(distinct_customers) FROM combined)
UNION ALL
SELECT 'Highest profit (price - freight)' AS achievement,
       seller_id,
       total_profit AS value
FROM combined
WHERE total_profit = (SELECT MAX(total_profit) FROM combined)
UNION ALL
SELECT 'Most distinct orders' AS achievement,
       seller_id,
       distinct_orders AS value
FROM combined
WHERE distinct_orders = (SELECT MAX(distinct_orders) FROM combined)
UNION ALL
SELECT 'Most 5-star ratings' AS achievement,
       seller_id,
       five_star_count AS value
FROM combined
WHERE five_star_count = (SELECT MAX(five_star_count) FROM combined);