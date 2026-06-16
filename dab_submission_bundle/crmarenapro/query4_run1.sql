WITH cleaned_cases AS (
    SELECT REPLACE(TRIM(c."OrderItemId__c"), '#', '') AS order_item_id,
           DATE_TRUNC('month', CAST(c."CreatedDate" AS TIMESTAMP))::DATE AS month_start
    FROM "support_db"."Case" c
    WHERE c."OrderItemId__c" IS NOT NULL
),
filtered_order_items AS (
    SELECT REPLACE(TRIM(oi."Id"), '#', '') AS order_item_id
    FROM "products_orders_db"."OrderItem" oi
    WHERE REPLACE(TRIM(oi."Product2Id"), '#', '') = '01tWt000006hVJdIAM'
),
joined_cases AS (
    SELECT cc.month_start
    FROM cleaned_cases cc
    JOIN filtered_order_items fo ON cc.order_item_id = fo.order_item_id
    WHERE cc.month_start >= DATE_TRUNC('month', DATE '2021-04-10') - INTERVAL '9' MONTH
      AND cc.month_start <= DATE_TRUNC('month', DATE '2021-04-10')
),
monthly_counts AS (
    SELECT month_start, COUNT(*) AS cnt
    FROM joined_cases
    GROUP BY month_start
)
SELECT CASE EXTRACT(MONTH FROM month_start)
         WHEN 1 THEN 'January'
         WHEN 2 THEN 'February'
         WHEN 3 THEN 'March'
         WHEN 4 THEN 'April'
         WHEN 5 THEN 'May'
         WHEN 6 THEN 'June'
         WHEN 7 THEN 'July'
         WHEN 8 THEN 'August'
         WHEN 9 THEN 'September'
         WHEN 10 THEN 'October'
         WHEN 11 THEN 'November'
         WHEN 12 THEN 'December'
       END AS month_name
FROM monthly_counts
ORDER BY cnt DESC
LIMIT 1;