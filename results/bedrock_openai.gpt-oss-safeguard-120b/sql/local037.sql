WITH category_payment_counts AS (
  SELECT p.product_category_name,
         pay.payment_type,
         COUNT(*) AS payment_count
  FROM olist_order_items oi
  JOIN olist_products p ON oi.product_id = p.product_id
  JOIN olist_order_payments pay ON oi.order_id = pay.order_id
  GROUP BY p.product_category_name, pay.payment_type
),
category_top_payment AS (
  SELECT product_category_name,
         payment_type,
         payment_count,
         ROW_NUMBER() OVER (PARTITION BY product_category_name ORDER BY payment_count DESC) AS rn
  FROM category_payment_counts
),
ranked_categories AS (
  SELECT product_category_name,
         payment_type,
         payment_count,
         ROW_NUMBER() OVER (ORDER BY payment_count DESC) AS overall_rn
  FROM category_top_payment
  WHERE rn = 1
)
SELECT product_category_name,
       payment_type,
       payment_count
FROM ranked_categories
WHERE overall_rn <= 3
ORDER BY payment_count DESC;