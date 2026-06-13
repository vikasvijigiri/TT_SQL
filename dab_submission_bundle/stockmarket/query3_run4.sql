WITH filtered_stocks AS (
    SELECT "Symbol",
           "Company Description"
    FROM "stockinfo_query_db"."stockinfo"
    WHERE "Market Category" IN ('Q','G','S')
      AND "Financial Status" IN ('D','E','G','H','J','K')
),
avg_volume_2008 AS (
    SELECT "_entity_name" AS "symbol",
           AVG("Volume") AS "avg_volume"
    FROM "all_stocktrade_query"
    WHERE TRY_CAST("Date" AS DATE) >= DATE '2008-01-01'
      AND TRY_CAST("Date" AS DATE) < DATE '2009-01-01'
      AND "Volume" IS NOT NULL
    GROUP BY "_entity_name"
)
SELECT COALESCE(
           NULLIF(regexp_extract(fs."Company Description",
                                 '^(.*?)(?:[.[:space:]]+)(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks)[[:space:]]',
                                 1), ''),
           fs."Symbol") AS "company_name",
       av."avg_volume"
FROM filtered_stocks fs
JOIN avg_volume_2008 av ON fs."Symbol" = av."symbol"
ORDER BY "company_name";