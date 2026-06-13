WITH eligible_symbols AS (
    SELECT DISTINCT s."Symbol"
    FROM "stockinfo_query_db"."stockinfo" s
    JOIN "all_stocktrade_query" t
      ON t."_entity_name" = s."Symbol"
    WHERE s."ETF" = 'Y'
      AND s."Listing Exchange" = 'P'
      AND TRY_CAST(t."Date" AS DATE) BETWEEN DATE '2015-01-01' AND DATE '2015-12-31'
      AND t."Adj Close" > 200
)
SELECT "Symbol", NULL::INTEGER AS total_etfs
FROM eligible_symbols
UNION ALL
SELECT 'TOTAL' AS "Symbol", COUNT(*)::INTEGER AS total_etfs
FROM eligible_symbols
ORDER BY "Symbol";