WITH contact AS (
    SELECT REPLACE(TRIM("AccountId"), '#', '') AS account_id
    FROM "core_crm_db"."Contact"
    WHERE REPLACE(TRIM("Id"), '#', '') = '003Wt00000Jqy8SIAR'
),
orders AS (
    SELECT REPLACE(TRIM("Id"), '#', '') AS order_id
    FROM "products_orders_db"."Order"
    WHERE REPLACE(TRIM("AccountId"), '#', '') = (SELECT account_id FROM contact)
      AND CAST("EffectiveDate" AS DATE) BETWEEN DATE '2021-06-01' AND DATE '2021-06-30'
),
order_items AS (
    SELECT REPLACE(TRIM("Product2Id"), '#', '') AS product_id
    FROM "products_orders_db"."OrderItem"
    WHERE REPLACE(TRIM("OrderId"), '#', '') IN (SELECT order_id FROM orders)
),
product AS (
    SELECT REPLACE(TRIM("Id"), '#', '') AS product_id
    FROM "products_orders_db"."Product2"
    WHERE LOWER(TRIM("Name")) LIKE '%ai processing unit%'
)
SELECT oi.product_id
FROM order_items oi
JOIN product p ON oi.product_id = p.product_id
LIMIT 1;