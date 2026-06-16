WITH trades_2018 AS (
    SELECT
        "Index" AS idx,
        "Open"::DOUBLE AS open_price,
        "Close"::DOUBLE AS close_price,
        TRY_CAST(regexp_extract("Date", '([0-9]{4})', 1) AS INTEGER) AS yr
    FROM "index_trade"
    WHERE TRY_CAST(regexp_extract("Date", '([0-9]{4})', 1) AS INTEGER) = 2018
),
north_american AS (
    SELECT 'IXIC' AS idx UNION ALL
    SELECT 'GSPTSE' UNION ALL
    SELECT 'NYA'
),
agg AS (
    SELECT
        t.idx,
        SUM(CASE WHEN t.close_price > t.open_price THEN 1 ELSE 0 END) AS up_days,
        SUM(CASE WHEN t.close_price < t.open_price THEN 1 ELSE 0 END) AS down_days
    FROM trades_2018 t
    JOIN north_american na ON t.idx = na.idx
    GROUP BY t.idx
)
SELECT idx AS "Index", up_days, down_days
FROM agg
WHERE up_days > down_days
ORDER BY idx;