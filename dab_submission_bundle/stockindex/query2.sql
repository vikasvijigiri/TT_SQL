WITH north_america(idx) AS (
    SELECT * FROM (VALUES ('IXIC'), ('NYA'), ('GSPTSE')) AS v(idx)
), filtered AS (
    SELECT "Index",
           "Open",
           "Close",
           CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END AS is_up,
           CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END AS is_down
    FROM "index_trade"
    WHERE TRY_CAST(regexp_extract("Date", '([0-9]{4})', 1) AS INTEGER) = 2018
      AND "Index" IN (SELECT idx FROM north_america)
)
SELECT "Index",
       SUM(is_up) AS up_days,
       SUM(is_down) AS down_days
FROM filtered
GROUP BY "Index"
HAVING SUM(is_up) > SUM(is_down)
ORDER BY "Index";