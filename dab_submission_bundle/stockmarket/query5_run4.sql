WITH daily_counts AS (
    SELECT t."_entity_name" AS symbol,
           COUNT(DISTINCT CAST(t."Date" AS DATE)) AS days_exceeding_range
    FROM "all_stocktrade_query" t
    WHERE CAST(t."Date" AS DATE) BETWEEN DATE '2019-01-01' AND DATE '2019-12-31'
      AND (t."High" - t."Low") > 0.20 * t."Low"
    GROUP BY t."_entity_name"
),
ranked AS (
    SELECT d.symbol,
           d.days_exceeding_range,
           s."Company Description",
           ROW_NUMBER() OVER (ORDER BY d.days_exceeding_range DESC) AS rn
    FROM daily_counts d
    JOIN "stockinfo_query_db"."stockinfo" s
      ON d.symbol = s."Symbol"
    WHERE s."Market Category" = 'S'
)
SELECT 
    regexp_extract(s."Company Description", '^(.*?)(?:\.\s+|\s+)+(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks)\s', 1) AS company_name,
    r.days_exceeding_range
FROM ranked r
JOIN "stockinfo_query_db"."stockinfo" s ON r.symbol = s."Symbol"
WHERE r.rn <= 5
ORDER BY r.days_exceeding_range DESC;