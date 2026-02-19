WITH years AS (
    SELECT 2021 AS yr UNION ALL SELECT 2022 UNION ALL SELECT 2023
),
months AS (
    SELECT 4 AS mo UNION ALL SELECT 5 UNION ALL SELECT 6
),
base AS (
    SELECT y.yr, m.mo
    FROM years y CROSS JOIN months m
),
monthly_counts AS (
    SELECT CAST(strftime('%Y', insert_date) AS INTEGER) AS yr,
           CAST(strftime('%m', insert_date) AS INTEGER) AS mo,
           COUNT(DISTINCT city_id) AS monthly_total
    FROM cities
    WHERE CAST(strftime('%Y', insert_date) AS INTEGER) BETWEEN 2021 AND 2023
      AND CAST(strftime('%m', insert_date) AS INTEGER) IN (4,5,6)
    GROUP BY yr, mo
),
combined AS (
    SELECT b.yr,
           b.mo,
           COALESCE(mc.monthly_total, 0) AS monthly_total
    FROM base b
    LEFT JOIN monthly_counts mc ON b.yr = mc.yr AND b.mo = mc.mo
),
with_running AS (
    SELECT yr,
           mo,
           monthly_total,
           SUM(monthly_total) OVER (PARTITION BY mo ORDER BY yr) AS running_total
    FROM combined
),
final AS (
    SELECT yr,
           mo,
           monthly_total,
           running_total,
           LAG(monthly_total) OVER (PARTITION BY mo ORDER BY yr) AS prev_monthly,
           LAG(running_total) OVER (PARTITION BY mo ORDER BY yr) AS prev_running
    FROM with_running
)
SELECT yr AS year,
       mo AS month,
       monthly_total,
       running_total,
       CASE WHEN prev_monthly IS NULL OR prev_monthly = 0 THEN NULL
            ELSE ((monthly_total - prev_monthly) * 100.0 / prev_monthly)
       END AS monthly_yoy_pct,
       CASE WHEN prev_running IS NULL OR prev_running = 0 THEN NULL
            ELSE ((running_total - prev_running) * 100.0 / prev_running)
       END AS running_yoy_pct
FROM final
WHERE yr IN (2022, 2023)
ORDER BY yr, mo;