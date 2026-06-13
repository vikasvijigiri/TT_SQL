WITH target_symbol AS (
    SELECT "Symbol"
    FROM "stockinfo_query_db"."stockinfo"
    WHERE "Company Description" ILIKE '%The RealReal, Inc.%'
    LIMIT 1
), trades_2020 AS (
    SELECT t."Adj Close"
    FROM "all_stocktrade_query" t
    JOIN target_symbol s ON t."_entity_name" = s."Symbol"
    WHERE CAST(t."Date" AS DATE) BETWEEN DATE '2020-01-01' AND DATE '2020-12-31'
)
SELECT MAX("Adj Close") AS "max_adj_close"
FROM trades_2020;