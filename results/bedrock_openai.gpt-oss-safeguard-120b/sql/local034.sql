WITH category_payments AS (
  SELECT
    p.product_category_name AS category,
    op.payment_type,
    COUNT(DISTINCT oi.order_id) AS payment_count
  FROM olist_order_items oi
  JOIN olist_products p ON oi.product_id = p.product_id
  JOIN olist_order_payments op ON oi.order_id = op.order_id
  GROUP BY p.product_category_name, op.payment_type
),
ranked AS (
  SELECT
    category,
    payment_type,
    payment_count,
    ROW_NUMBER() OVER (PARTITION BY category ORDER BY payment_count DESC) AS rn
  FROM category_payments
)
SELECT AVG(payment_count) AS average_payments_per_category
FROM ranked
WHERE rn = 1;