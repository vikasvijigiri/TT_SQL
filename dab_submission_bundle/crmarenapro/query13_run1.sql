WITH "date_window" AS (
    SELECT CAST('2022-11-25' AS DATE) AS ref_date,
           CAST('2022-11-25' AS DATE) - INTERVAL '5 months' AS start_date
),
"filtered_orders" AS (
    SELECT REPLACE(TRIM(o."OwnerId"), '#', '') AS agent_id,
           CAST(oi."Quantity" AS DOUBLE) * CAST(oi."UnitPrice" AS DOUBLE) AS line_sales
    FROM "products_orders_db"."Order" o
    JOIN "products_orders_db"."OrderItem" oi
      ON REPLACE(TRIM(oi."OrderId"), '#', '') = REPLACE(TRIM(o."Id"), '#', '')
    JOIN "sales_pipeline"."Contract" c
      ON REPLACE(TRIM(c."AccountId"), '#', '') = REPLACE(TRIM(o."AccountId"), '#', '')
    JOIN "date_window" dw
      ON CAST(o."EffectiveDate" AS DATE) BETWEEN dw.start_date AND dw.ref_date
     AND CAST(c."CompanySignedDate" AS DATE) BETWEEN dw.start_date AND dw.ref_date
),
"agg" AS (
    SELECT agent_id,
           SUM(line_sales) AS total_sales
    FROM "filtered_orders"
    GROUP BY agent_id
)
SELECT agent_id AS Id
FROM "agg"
ORDER BY total_sales DESC
LIMIT 1;