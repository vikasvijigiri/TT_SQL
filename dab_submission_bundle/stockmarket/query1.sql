WITH realreal_symbol AS (
    SELECT "Symbol"
    FROM "stockinfo_query_db"."stockinfo"
    WHERE "Company Description" ILIKE '%The RealReal, Inc.%' OR "Company Description" ILIKE '%RealReal%'
    LIMIT 1
)
SELECT MAX(t."Adj Close") AS max_adj_close_2020
FROM "all_stocktrade_query" AS t
JOIN realreal_symbol AS s ON t."_entity_name" = s."Symbol"
WHERE CAST(t."Date" AS DATE) BETWEEN DATE '2020-01-01' AND DATE '2020-12-31';