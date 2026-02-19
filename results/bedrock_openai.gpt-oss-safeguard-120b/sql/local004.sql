WITH customer_summary AS (
  SELECT
    o.customer_id,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(op.payment_value) AS total_payment,
    MIN(o.order_purchase_timestamp) AS earliest_date,
    MAX(o.order_purchase_timestamp) AS latest_date
  FROM orders o
  JOIN order_payments op ON o.order_id = op.order_id
  GROUP BY o.customer_id
),
customer_metrics AS (
  SELECT
    customer_id,
    order_count,
    total_payment / order_count AS average_payment_per_order,
    CASE
      WHEN (julianday(latest_date) - julianday(earliest_date)) < 7 THEN 1.0
      ELSE (julianday(latest_date) - julianday(earliest_date)) / 7.0
    END AS customer_lifespan_weeks
  FROM customer_summary
)
SELECT
  customer_id,
  order_count,
  average_payment_per_order,
  customer_lifespan_weeks
FROM customer_metrics
ORDER BY average_payment_per_order DESC
LIMIT 3;