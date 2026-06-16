WITH cleaned_contact AS (
    SELECT TRIM(REPLACE("Id", '#', '')) AS clean_contact_id,
           TRIM(REPLACE("AccountId", '#', '')) AS clean_account_id
    FROM "core_crm_db"."Contact"
    WHERE TRIM(REPLACE("Id", '#', '')) = '003Wt00000Jqy8SIAR'
)
SELECT TRIM(REPLACE(p."Id", '#', '')) AS product_id
FROM cleaned_contact c
JOIN "products_orders_db"."Order" o
    ON TRIM(REPLACE(o."AccountId", '#', '')) = c.clean_account_id
JOIN "products_orders_db"."OrderItem" oi
    ON TRIM(REPLACE(oi."OrderId", '#', '')) = TRIM(REPLACE(o."Id", '#', ''))
JOIN "products_orders_db"."Product2" p
    ON TRIM(REPLACE(p."Id", '#', '')) = TRIM(REPLACE(oi."Product2Id", '#', ''))
WHERE CAST(o."EffectiveDate" AS DATE) BETWEEN DATE '2021-06-01' AND DATE '2021-06-30'
  AND LOWER(p."Name") LIKE '%ai processing unit%';