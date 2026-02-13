WITH ValidYears AS (
    SELECT DISTINCT CAST(year AS INTEGER) AS year
    FROM Movie
    WHERE year IS NOT NULL AND year != '' AND year GLOB '[0-9]*'
),
TenYearPeriods AS (
    SELECT vy.year AS start_year, COUNT(m.MID) AS total_movies
    FROM ValidYears vy
    JOIN Movie m ON CAST(m.year AS INTEGER) BETWEEN vy.year AND vy.year + 9
    WHERE m.year GLOB '[0-9]*'
    GROUP BY vy.year
)
SELECT start_year, total_movies
FROM TenYearPeriods
ORDER BY total_movies DESC
LIMIT 1;