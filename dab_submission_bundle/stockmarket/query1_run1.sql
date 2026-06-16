WITH target_symbol AS (
    SELECT "Symbol"
    FROM "stockinfo_query_db"."stockinfo"
    WHERE "Company Description" ILIKE '%The RealReal, Inc.%' OR "Company Description" ILIKE '%RealReal%'
    LIMIT 1
)
SELECT MAX("Adj Close") AS "max_adj_close"
FROM "all_stocktrade_query"
WHERE "_entity_name" = (SELECT "Symbol" FROM target_symbol)
  AND CAST("Date" AS DATE) BETWEEN DATE '2020-01-01' AND DATE '2020-12-31';