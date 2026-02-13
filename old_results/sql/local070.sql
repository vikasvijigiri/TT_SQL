WITH DateStreaks AS (
  SELECT 
    c.city_name,
    c.insert_date AS date,
    CASE WHEN JULIANDAY(c.insert_date) - JULIANDAY(LAG(c.insert_date) OVER (PARTITION BY c.city_name ORDER BY c.insert_date)) = 1 THEN 0 ELSE 1 END AS is_new_streak
  FROM 
    cities c
  WHERE 
    c.country_code_2 = 'cn' AND
    c.insert_date BETWEEN '2021-07-01' AND '2021-07-31'
),
StreakGroups AS (
  SELECT 
    city_name,
    date,
    SUM(is_new_streak) OVER (PARTITION BY city_name ORDER BY date) AS streak_id
  FROM 
    DateStreaks
),
StreakLengths AS (
  SELECT 
    city_name,
    streak_id,
    COUNT(*) AS streak_length,
    MIN(date) AS start_date,
    MAX(date) AS end_date
  FROM 
    StreakGroups
  GROUP BY 
    city_name, streak_id
),
RankedStreaks AS (
  SELECT 
    city_name,
    streak_id,
    streak_length,
    start_date,
    end_date,
    DENSE_RANK() OVER (ORDER BY streak_length ASC) AS shortest_rank,
    DENSE_RANK() OVER (ORDER BY streak_length DESC) AS longest_rank
  FROM 
    StreakLengths
),
ShortestStreak AS (
  SELECT 
    city_name,
    streak_id,
    start_date,
    end_date
  FROM 
    RankedStreaks
  WHERE 
    shortest_rank = 1
),
LongestStreak AS (
  SELECT 
    city_name,
    streak_id,
    start_date,
    end_date
  FROM 
    RankedStreaks
  WHERE 
    longest_rank = 1
)
SELECT DISTINCT
  sg.date,
  UPPER(SUBSTR(sg.city_name, 1, 1)) || LOWER(SUBSTR(sg.city_name, 2)) AS city_name
FROM 
  StreakGroups sg
JOIN 
  ShortestStreak ss ON sg.streak_id = ss.streak_id AND sg.city_name = ss.city_name AND sg.date BETWEEN ss.start_date AND ss.end_date
UNION ALL
SELECT DISTINCT
  sg.date,
  UPPER(SUBSTR(sg.city_name, 1, 1)) || LOWER(SUBSTR(sg.city_name, 2)) AS city_name
FROM 
  StreakGroups sg
JOIN 
  LongestStreak ls ON sg.streak_id = ls.streak_id AND sg.city_name = ls.city_name AND sg.date BETWEEN ls.start_date AND ls.end_date
ORDER BY 
  date;