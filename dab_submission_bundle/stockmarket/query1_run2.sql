WITH target_symbols AS (
    SELECT "Symbol"
    FROM "stockinfo_query_db"."stockinfo"
    WHERE "Company Description" ILIKE '%The RealReal%'
)
SELECT MAX(q."Adj Close") AS max_adj_close_2020
FROM "all_stocktrade_query" q
JOIN target_symbols t ON q."_entity_name" = t."Symbol"
WHERE q."Date" >= '2020-01-01' AND q."Date" <= '2020-12-31';