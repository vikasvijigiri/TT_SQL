WITH eligible_etfs AS (
    SELECT DISTINCT s."Symbol"
    FROM "stockinfo" s
    JOIN "all_stocktrade_query" t
      ON t."_entity_name" = s."Symbol"
    WHERE s."ETF" = 'Y'
      AND s."Listing Exchange" = 'P'
      AND TRY_CAST(t."Date" AS DATE) >= DATE '2015-01-01'
      AND TRY_CAST(t."Date" AS DATE) < DATE '2016-01-01'
      AND t."Adj Close" > 200
), total_etfs AS (
    SELECT COUNT(*) AS cnt FROM eligible_etfs
)
SELECT e."Symbol", NULL::INTEGER AS "total_etfs"
FROM eligible_etfs e
UNION ALL
SELECT 'TOTAL' AS "Symbol", cnt AS "total_etfs"
FROM total_etfs
ORDER BY "Symbol";