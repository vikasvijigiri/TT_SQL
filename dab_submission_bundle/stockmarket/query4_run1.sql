WITH daily_counts AS (
    SELECT t."_entity_name" AS symbol,
           SUM(CASE WHEN t."Close" > t."Open" THEN 1 ELSE 0 END) AS up_days,
           SUM(CASE WHEN t."Close" < t."Open" THEN 1 ELSE 0 END) AS down_days
    FROM "all_stocktrade_query" t
    WHERE CAST(t."Date" AS DATE) BETWEEN DATE '2017-01-01' AND DATE '2017-12-31'
    GROUP BY t."_entity_name"
),
eligible AS (
    SELECT symbol, up_days, down_days
    FROM daily_counts
    WHERE up_days > down_days
),
ranked AS (
    SELECT 
        COALESCE(
            NULLIF(regexp_extract(si."Company Description",
                '^(.*?)(?:[.][[:space:]]|[[:space:]]+)(?:is|specializes|focuses|operates|designs|develops|manufactures|provides|engages|was|pioneers|pioneering|dedicated|offers|seeks|tracks)[[:space:]]',
                1), ''),
            si."Company Description"
        ) AS company_name,
        e.up_days,
        ROW_NUMBER() OVER (ORDER BY e.up_days DESC, company_name ASC) AS rn
    FROM eligible e
    JOIN "stockinfo_query_db"."stockinfo" si ON si."Symbol" = e.symbol
    WHERE si."ETF" = 'N' AND si."Listing Exchange" = 'N'
)
SELECT company_name
FROM ranked
WHERE rn <= 5
ORDER BY rn;