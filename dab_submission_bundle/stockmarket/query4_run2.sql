WITH daily_up_down AS (
  SELECT
    t."_entity_name" AS symbol,
    SUM(CASE WHEN t."Close" > t."Open" THEN 1 ELSE 0 END) AS up_days,
    SUM(CASE WHEN t."Close" < t."Open" THEN 1 ELSE 0 END) AS down_days
  FROM "all_stocktrade_query" t
  WHERE CAST(t."Date" AS DATE) BETWEEN DATE '2017-01-01' AND DATE '2017-12-31'
  GROUP BY t."_entity_name"
),
eligible AS (
  SELECT
    d.symbol,
    d.up_days,
    d.down_days,
    si."Company Description"
  FROM daily_up_down d
  JOIN "stockinfo" si ON si."Symbol" = d.symbol
  WHERE si."ETF" = 'N'
    AND si."Listing Exchange" = 'N'
    AND d.up_days > d.down_days
)
SELECT
  TRIM(COALESCE(NULLIF(regexp_extract("Company Description", '^(.*?)(?:\.|\s)+(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks)\s', 1), ''), "Company Description")) AS company_name
FROM eligible
ORDER BY up_days DESC, company_name ASC
LIMIT 5;