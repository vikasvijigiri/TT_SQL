SELECT p."Id" AS "ProductId"
FROM "core_crm_db"."Contact" c
JOIN "products_orders_db"."Order" o ON TRIM(REPLACE(c."AccountId", '#', '')) = TRIM(REPLACE(o."AccountId", '#', ''))
JOIN "products_orders_db"."OrderItem" oi ON oi."OrderId" = o."Id"
JOIN "products_orders_db"."Product2" p ON p."Id" = oi."Product2Id"
WHERE TRIM(REPLACE(c."Id", '#', '')) = '003Wt00000Jqy8SIAR'
  AND CAST(o."EffectiveDate" AS DATE) BETWEEN DATE '2021-06-01' AND DATE '2021-06-30'
  AND (LOWER(TRIM(p."Name")) LIKE '%ai%' OR LOWER(TRIM(COALESCE(p."External_ID__c", ''))) LIKE '%ai%')
QUALIFY ROW_NUMBER() OVER (PARTITION BY c."Id" ORDER BY CAST(o."EffectiveDate" AS DATE) DESC) = 1;