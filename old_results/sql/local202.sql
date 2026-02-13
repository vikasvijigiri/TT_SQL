WITH state_stats AS (
  SELECT
    state,
    COUNT(*) AS total_pop,
    SUM(CASE WHEN aggressive = 0 THEN 1 ELSE 0 END) AS friendly_cnt,
    SUM(CASE WHEN aggressive = 1 THEN 1 ELSE 0 END) AS hostile_cnt,
    AVG(age) AS avg_age
  FROM alien_data
  GROUP BY state
),
ranked AS (
  SELECT
    state,
    total_pop,
    friendly_cnt,
    hostile_cnt,
    avg_age,
    ROW_NUMBER() OVER (ORDER BY total_pop DESC) AS rn
  FROM state_stats
)
SELECT COUNT(*) AS qualifying_states
FROM ranked
WHERE rn <= 10
  AND friendly_cnt > hostile_cnt
  AND avg_age > 200;