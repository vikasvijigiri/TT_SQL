WITH filtered_info AS (
  SELECT "Symbol",
         "Company Description"
  FROM "stockinfo_query_db"."stockinfo"
  WHERE "Market Category" IN ('Q','G','S')
    AND "Financial Status" IN ('D','E','G','H','J','K')
),
avg_volume_2008 AS (
  SELECT "_entity_name" AS "symbol",
         AVG("Volume")::DOUBLE AS "avg_volume"
  FROM "all_stocktrade_query"
  WHERE TRY_CAST("Date" AS DATE) >= DATE '2008-01-01'
    AND TRY_CAST("Date" AS DATE) < DATE '2009-01-01'
    AND "Volume" IS NOT NULL
  GROUP BY "_entity_name"
)
SELECT
  COALESCE(
    regexp_extract("Company Description",
      '^(.*?)(?:[.]|[[:space:]])+(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks)[[:space:]]',
      1),
    "Company Description"
  ) AS "company_name",
  av."avg_volume"
FROM filtered_info fi
JOIN avg_volume_2008 av ON fi."Symbol" = av."symbol"
WHERE av."avg_volume" IS NOT NULL
ORDER BY "company_name";