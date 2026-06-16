WITH daily_counts AS (
    SELECT t."_entity_name" AS symbol,
           COUNT(*) AS days_exceeding_range
    FROM "all_stocktrade_query" t
    WHERE CAST(t."Date" AS DATE) BETWEEN DATE '2019-01-01' AND DATE '2019-12-31'
      AND t."High" > t."Low" * 1.20
    GROUP BY t."_entity_name"
),
nasdaq_capital AS (
    SELECT s."Symbol" AS symbol,
           regexp_extract(s."Company Description", '^(.*?)(?:\\.|\\s)+(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks)\\s', 1) AS company_name
    FROM "stockinfo_query_db"."stockinfo" s
    WHERE s."Market Category" = 'S'
)
SELECT n.company_name
FROM daily_counts d
JOIN nasdaq_capital n ON d.symbol = n.symbol
ORDER BY d.days_exceeding_range DESC
LIMIT 5;