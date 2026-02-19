WITH delivered_orders AS (
    SELECT o.order_id,
           o.customer_id,
           o.order_purchase_timestamp
    FROM orders o
    WHERE LOWER(o.order_status) = 'delivered'
),
order_totals AS (
    SELECT d.order_id,
           d.customer_id,
           d.order_purchase_timestamp,
           SUM(oi.price) AS order_total
    FROM delivered_orders d
    JOIN order_items oi ON d.order_id = oi.order_id
    GROUP BY d.order_id, d.customer_id, d.order_purchase_timestamp
),
customer_agg AS (
    SELECT c.customer_unique_id,
           SUM(ot.order_total) AS total_spend,
           COUNT(DISTINCT ot.order_id) AS order_count,
           MAX(ot.order_purchase_timestamp) AS latest_purchase_timestamp
    FROM order_totals ot
    JOIN customers c ON ot.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
rfm_scores AS (
    SELECT ca.customer_unique_id,
           ca.total_spend,
           ca.order_count,
           ca.latest_purchase_timestamp,
           CAST(julianday('now') - julianday(ca.latest_purchase_timestamp) AS INTEGER) AS recency_days,
           ca.total_spend / ca.order_count AS avg_sales_per_order,
           (6 - NTILE(5) OVER (ORDER BY CAST(julianday('now') - julianday(ca.latest_purchase_timestamp) AS INTEGER))) AS recency_score,
           NTILE(5) OVER (ORDER BY ca.order_count) AS frequency_score,
           NTILE(5) OVER (ORDER BY ca.total_spend) AS monetary_score,
           ((6 - NTILE(5) OVER (ORDER BY CAST(julianday('now') - julianday(ca.latest_purchase_timestamp) AS INTEGER))) ||
            NTILE(5) OVER (ORDER BY ca.order_count) ||
            NTILE(5) OVER (ORDER BY ca.total_spend)) AS rfm_segment
    FROM customer_agg ca
)
SELECT rfm_segment,
       COUNT(*) AS customer_count,
       AVG(avg_sales_per_order) AS segment_average_sales_per_order
FROM rfm_scores
GROUP BY rfm_segment
ORDER BY rfm_segment;