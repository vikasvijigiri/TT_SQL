WITH target AS (
    SELECT "Symbol"
    FROM "stockinfo"
    WHERE "Company Description" LIKE '%The RealReal, Inc.%'
    LIMIT 1
)
SELECT MAX("Adj Close") AS "max_adj_close"
FROM "all_stocktrade_query"
WHERE "_entity_name" = (SELECT "Symbol" FROM target)
  AND "Date" BETWEEN '2020-01-01' AND '2020-12-31';