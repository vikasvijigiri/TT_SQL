WITH filtered AS (
    SELECT insert_date,
           MIN(city_name) AS city_name
    FROM cities
    WHERE LOWER(country_code_2) = 'cn'
      AND insert_date >= '2021-07-01' AND insert_date <= '2021-07-31'
    GROUP BY insert_date
),
ordered AS (
    SELECT insert_date,
           city_name,
           LAG(insert_date) OVER (ORDER BY insert_date) AS prev_date
    FROM filtered
),
streaks AS (
    SELECT insert_date,
           city_name,
           CASE 
               WHEN prev_date IS NULL THEN 0
               WHEN CAST(julianday(insert_date) - julianday(prev_date) AS INTEGER) = 1 THEN 0
               ELSE 1
           END AS new_streak_flag
    FROM ordered
),
grouped AS (
    SELECT insert_date,
           city_name,
           SUM(new_streak_flag) OVER (ORDER BY insert_date ROWS UNBOUNDED PRECEDING) AS streak_id
    FROM streaks
),
lengths AS (
    SELECT insert_date,
           city_name,
           streak_id,
           COUNT(*) OVER (PARTITION BY streak_id) AS streak_len
    FROM grouped
),
bounds AS (
    SELECT MIN(streak_len) AS min_len,
           MAX(streak_len) AS max_len
    FROM lengths
)
SELECT l.insert_date,
       upper(substr(l.city_name, 1, 1)) || lower(substr(l.city_name, 2)) AS city_name
FROM lengths l
JOIN bounds b ON l.streak_len = b.min_len OR l.streak_len = b.max_len
ORDER BY l.insert_date;