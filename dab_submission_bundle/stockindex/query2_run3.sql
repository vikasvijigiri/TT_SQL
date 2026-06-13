WITH north_american_indices AS (
    SELECT 'IXIC' AS "Index"
    UNION ALL SELECT 'NYA'
    UNION ALL SELECT 'GSPTSE'
    UNION ALL SELECT 'DJI'
    UNION ALL SELECT 'SPX'
    UNION ALL SELECT 'RUT'
    UNION ALL SELECT 'VIX'
),
filtered_trade AS (
    SELECT it."Index",
           it."Open",
           it."Close",
           TRY_CAST(regexp_extract(it."Date", '([0-9]{4})', 1) AS INTEGER) AS yr
    FROM "index_trade" it
    JOIN north_american_indices na ON it."Index" = na."Index"
    WHERE TRY_CAST(regexp_extract(it."Date", '([0-9]{4})', 1) AS INTEGER) = 2018
),
up_down_counts AS (
    SELECT "Index",
           SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) AS up_days,
           SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) AS down_days
    FROM filtered_trade
    GROUP BY "Index"
)
SELECT "Index", up_days, down_days
FROM up_down_counts
WHERE up_days > down_days
ORDER BY "Index";