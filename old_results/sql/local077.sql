WITH FilteredInterestMetrics AS (
    SELECT *
    FROM interest_metrics
    WHERE (_year = 2018 AND _month >= 9) OR (_year = 2019 AND _month <= 8)
),
InterestWithNames AS (
    SELECT fim.*, im.interest_name
    FROM FilteredInterestMetrics fim
    JOIN interest_map im ON fim.interest_id = im.id
),
AverageComposition AS (
    SELECT 
        month_year,
        interest_name,
        AVG(composition / CAST(index_value AS REAL)) AS avg_composition
    FROM InterestWithNames
    GROUP BY month_year, interest_name
),
MonthlyMaxIndexComposition AS (
    SELECT 
        ac.month_year,
        ac.interest_name,
        ac.avg_composition AS max_index_composition
    FROM AverageComposition ac
    JOIN (
        SELECT month_year, MAX(avg_composition) AS max_avg_composition
        FROM AverageComposition
        GROUP BY month_year
    ) max_ac ON ac.month_year = max_ac.month_year AND ac.avg_composition = max_ac.max_avg_composition
),
RollingAverage AS (
    SELECT 
        t1.month_year,
        t1.interest_name,
        t1.max_index_composition,
        (t1.max_index_composition + COALESCE(t2.max_index_composition, 0) + COALESCE(t3.max_index_composition, 0)) / 
        (1 + CASE WHEN t2.max_index_composition IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN t3.max_index_composition IS NOT NULL THEN 1 ELSE 0 END) AS rolling_avg,
        t2.interest_name AS prev_month_interest,
        t2.max_index_composition AS prev_month_composition,
        t3.interest_name AS prev_two_month_interest,
        t3.max_index_composition AS prev_two_month_composition
    FROM MonthlyMaxIndexComposition t1
    LEFT JOIN MonthlyMaxIndexComposition t2 ON 
        (CAST(SUBSTR(t1.month_year, 0, 5) AS INTEGER) * 12 + CAST(SUBSTR(t1.month_year, 6, 2) AS INTEGER)) - 1 = 
        (CAST(SUBSTR(t2.month_year, 0, 5) AS INTEGER) * 12 + CAST(SUBSTR(t2.month_year, 6, 2) AS INTEGER))
    LEFT JOIN MonthlyMaxIndexComposition t3 ON 
        (CAST(SUBSTR(t1.month_year, 0, 5) AS INTEGER) * 12 + CAST(SUBSTR(t1.month_year, 6, 2) AS INTEGER)) - 2 = 
        (CAST(SUBSTR(t3.month_year, 0, 5) AS INTEGER) * 12 + CAST(SUBSTR(t3.month_year, 6, 2) AS INTEGER))
)
SELECT *
FROM RollingAverage
ORDER BY month_year;