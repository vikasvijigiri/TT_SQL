WITH filtered_info AS (
    SELECT "Symbol",
           COALESCE(
               NULLIF(regexp_extract("Company Description", '^(.*?)(?:[.| ]+)(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks) ', 1), ''),
               "Company Description"
           ) AS company_name
    FROM "stockinfo_query_db"."stockinfo"
    WHERE "Market Category" IN ('Q','G','S')
      AND "Financial Status" IN ('D','E','G','H','J','K')
), avg_vol AS (
    SELECT "_entity_name" AS symbol,
           AVG("Volume")::DOUBLE AS avg_volume
    FROM "all_stocktrade_query"
    WHERE TRY_CAST("Date" AS DATE) >= DATE '2008-01-01'
      AND TRY_CAST("Date" AS DATE) < DATE '2009-01-01'
      AND "Volume" IS NOT NULL
    GROUP BY "_entity_name"
)
SELECT fi.company_name,
       av.avg_volume
FROM filtered_info fi
JOIN avg_vol av ON fi."Symbol" = av.symbol
ORDER BY fi.company_name;