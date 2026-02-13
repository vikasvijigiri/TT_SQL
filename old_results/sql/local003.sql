WITH latest_purchase AS (
    SELECT c.customer_unique_id, 
           MAX(o.order_purchase_timestamp) AS last_purchase_date
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
),
max_purchase_date AS (
    SELECT MAX(last_purchase_date) AS max_date
    FROM latest_purchase
),
recency AS (
    SELECT lp.customer_unique_id, 
           JULIANDAY(mp.max_date) - JULIANDAY(lp.last_purchase_date) AS recency_days
    FROM latest_purchase lp, max_purchase_date mp
),
frequency AS (
    SELECT c.customer_unique_id, 
           COUNT(DISTINCT o.order_id) AS order_count
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
),
monetary AS (
    SELECT c.customer_unique_id, 
           SUM(oi.price) AS total_spend
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
),
rfm AS (
    SELECT r.customer_unique_id, 
           r.recency_days, 
           f.order_count, 
           m.total_spend,
           CASE 
               WHEN r.recency_days <= 30 THEN 'Recent'
               WHEN r.recency_days <= 90 THEN 'Active'
               ELSE 'Inactive'
           END AS recency_segment,
           CASE 
               WHEN f.order_count >= 10 THEN 'Frequent'
               WHEN f.order_count >= 5 THEN 'Regular'
               ELSE 'Occasional'
           END AS frequency_segment,
           CASE 
               WHEN m.total_spend >= 1000 THEN 'High'
               WHEN m.total_spend >= 500 THEN 'Medium'
               ELSE 'Low'
           END AS monetary_segment
    FROM recency r
    JOIN frequency f ON r.customer_unique_id = f.customer_unique_id
    JOIN monetary m ON r.customer_unique_id = m.customer_unique_id
),
rfm_segments AS (
    SELECT customer_unique_id, 
           recency_segment || '-' || frequency_segment || '-' || monetary_segment AS rfm_segment
    FROM rfm
),
avg_sales_per_order AS (
    SELECT c.customer_unique_id, 
           m.total_spend / CAST(f.order_count AS REAL) AS avg_sales
    FROM monetary m
    JOIN frequency f ON m.customer_unique_id = f.customer_unique_id
)
SELECT rfm.rfm_segment, 
       AVG(aso.avg_sales) AS avg_sales_per_order
FROM rfm_segments rfm
JOIN avg_sales_per_order aso ON rfm.customer_unique_id = aso.customer_unique_id
GROUP BY rfm.rfm_segment
ORDER BY avg_sales_per_order DESC;