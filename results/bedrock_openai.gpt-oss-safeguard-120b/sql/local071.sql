WITH filtered AS (
    SELECT country_code_2, DATE(insert_date) AS insert_day
    FROM cities
    WHERE insert_date >= '2022-06-01' AND insert_date < '2022-07-01'
    GROUP BY country_code_2, insert_day
), numbered AS (
    SELECT country_code_2,
           insert_day,
           ROW_NUMBER() OVER (PARTITION BY country_code_2 ORDER BY insert_day) AS rn
    FROM filtered
), grouped AS (
    SELECT country_code_2,
           DATE(insert_day, '-' || rn || ' day') AS grp,
           COUNT(*) AS streak_length
    FROM numbered
    GROUP BY country_code_2, grp
), max_per_country AS (
    SELECT country_code_2, MAX(streak_length) AS max_streak
    FROM grouped
    GROUP BY country_code_2
), overall_max AS (
    SELECT MAX(max_streak) AS overall_max FROM max_per_country
)
SELECT mpc.country_code_2
FROM max_per_country mpc
JOIN overall_max om ON mpc.max_streak = om.overall_max;