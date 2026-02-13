WITH MonthlyCityCounts AS (
    SELECT 
        strftime('%Y', insert_date) AS year, 
        strftime('%m', insert_date) AS month, 
        COUNT(city_id) AS monthly_total
    FROM cities
    WHERE strftime('%m', insert_date) IN ('04', '05', '06')
      AND strftime('%Y', insert_date) IN ('2021', '2022', '2023')
    GROUP BY year, month
),
CumulativeCityCounts AS (
    SELECT 
        year, 
        month, 
        monthly_total,
        SUM(monthly_total) OVER (PARTITION BY month ORDER BY year) AS running_total
    FROM MonthlyCityCounts
),
YearOverYearGrowth AS (
    SELECT 
        ccc.year, 
        ccc.month, 
        ccc.monthly_total, 
        ccc.running_total,
        LAG(ccc.monthly_total) OVER (PARTITION BY ccc.month ORDER BY ccc.year) AS prev_monthly_total,
        LAG(ccc.running_total) OVER (PARTITION BY ccc.month ORDER BY ccc.year) AS prev_running_total
    FROM CumulativeCityCounts ccc
),
FinalResults AS (
    SELECT 
        year, 
        month, 
        monthly_total, 
        running_total,
        CASE WHEN prev_monthly_total IS NOT NULL AND prev_monthly_total != 0 THEN 
            ((CAST(monthly_total AS REAL) - CAST(prev_monthly_total AS REAL)) / CAST(prev_monthly_total AS REAL)) * 100
        ELSE NULL END AS monthly_growth_percentage,
        CASE WHEN prev_running_total IS NOT NULL AND prev_running_total != 0 THEN 
            ((CAST(running_total AS REAL) - CAST(prev_running_total AS REAL)) / CAST(prev_running_total AS REAL)) * 100
        ELSE NULL END AS running_growth_percentage
    FROM YearOverYearGrowth
    WHERE year IN ('2022', '2023')
)
SELECT * FROM FinalResults;