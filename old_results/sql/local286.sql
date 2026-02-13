WITH seller_sales AS (
    SELECT
        oi.seller_id,
        COUNT(*) AS total_quantity,
        SUM(oi.price) AS total_sales,
        AVG(oi.price) AS avg_price,
        AVG(julianday(oi.shipping_limit_date) - julianday(o.order_approved_at)) AS avg_packing_time
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    GROUP BY oi.seller_id
    HAVING COUNT(*) > 100
),
seller_reviews AS (
    SELECT
        oi.seller_id,
        AVG(orv.review_score) AS avg_review_score
    FROM order_items oi
    JOIN order_reviews orv ON oi.order_id = orv.order_id
    GROUP BY oi.seller_id
),
seller_metrics AS (
    SELECT
        ss.seller_id,
        ss.total_sales,
        ss.avg_price,
        sr.avg_review_score,
        ss.avg_packing_time
    FROM seller_sales ss
    LEFT JOIN seller_reviews sr ON ss.seller_id = sr.seller_id
),
category_sales AS (
    SELECT
        p.product_category_name,
        SUM(oi.price) AS category_sales
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    GROUP BY p.product_category_name
),
top_category AS (
    SELECT
        pcnt.product_category_name_english
    FROM category_sales cs
    JOIN product_category_name_translation pcnt ON cs.product_category_name = pcnt.product_category_name
    ORDER BY cs.category_sales DESC
    LIMIT 1
)
SELECT
    sm.seller_id,
    sm.total_sales,
    sm.avg_price,
    sm.avg_review_score,
    sm.avg_packing_time,
    tc.product_category_name_english AS top_category_name_english
FROM seller_metrics sm
CROSS JOIN top_category tc;