WITH north_american_indices AS (
    SELECT 'IXIC' AS "Index", 'NASDAQ' AS "Exchange" UNION ALL
    SELECT 'NYA', 'New York Stock Exchange' UNION ALL
    SELECT 'GSPTSE', 'Toronto Stock Exchange'
),
filtered_trades AS (
    SELECT it."Index",
           CASE WHEN it."Close" > it."Open" THEN 1 ELSE 0 END AS up_flag,
           CASE WHEN it."Close" < it."Open" THEN 1 ELSE 0 END AS down_flag
    FROM "index_trade" AS it
    JOIN north_american_indices AS nai ON it."Index" = nai."Index"
    WHERE TRY_CAST(regexp_extract(it."Date", '([0-9]{4})', 1) AS INTEGER) = 2018
)
SELECT "Index",
       SUM(up_flag) AS up_days,
       SUM(down_flag) AS down_days
FROM filtered_trades
GROUP BY "Index"
HAVING SUM(up_flag) > SUM(down_flag)
ORDER BY "Index";