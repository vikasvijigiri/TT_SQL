WITH troubled_companies AS (
    SELECT "Symbol",
           COALESCE(NULLIF(regexp_extract("Company Description", '^(.*?)(?:\\.|\\s)+(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks)\\s', 1), ''), "Symbol") AS company_name
    FROM "stockinfo_query_db"."stockinfo"
    WHERE "Listing Exchange" = 'Q'
      AND "Financial Status" IN ('D','E','G','H','J','K')
), avg_volume_2008 AS (
    SELECT "_entity_name" AS symbol,
           AVG("Volume")::DOUBLE AS avg_volume
    FROM "all_stocktrade_query"
    WHERE TRY_CAST("Date" AS DATE) >= DATE '2008-01-01'
      AND TRY_CAST("Date" AS DATE) < DATE '2009-01-01'
      AND "Volume" IS NOT NULL
    GROUP BY "_entity_name"
    HAVING AVG("Volume") IS NOT NULL
)
SELECT tc.company_name,
       av.avg_volume
FROM troubled_companies tc
JOIN avg_volume_2008 av ON tc."Symbol" = av.symbol
ORDER BY tc.company_name;