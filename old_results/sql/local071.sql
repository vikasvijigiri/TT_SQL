WITH FilteredCities AS (
    SELECT c.city_id, c.country_code_2, c.insert_date
    FROM cities c
    WHERE strftime('%Y-%m', c.insert_date) = '2022-06'
),
ConsecutiveDates AS (
    SELECT 
        city_id, 
        country_code_2, 
        insert_date,
        COALESCE(JULIANDAY(insert_date) - JULIANDAY(LAG(insert_date) OVER (PARTITION BY country_code_2 ORDER BY insert_date)), 1) AS day_diff
    FROM FilteredCities
),
RankedCities AS (
    SELECT 
        city_id, 
        country_code_2, 
        insert_date,
        SUM(CASE WHEN day_diff = 1 THEN 0 ELSE 1 END) OVER (PARTITION BY country_code_2 ORDER BY insert_date) AS streak_group
    FROM ConsecutiveDates
),
Streaks AS (
    SELECT 
        country_code_2, 
        streak_group,
        COUNT(*) AS streak_length
    FROM RankedCities
    GROUP BY country_code_2, streak_group
),
MaxStreaks AS (
    SELECT 
        country_code_2, 
        MAX(streak_length) AS max_streak
    FROM Streaks
    GROUP BY country_code_2
)
SELECT country_code_2
FROM MaxStreaks
WHERE max_streak = (SELECT MAX(max_streak) FROM MaxStreaks);