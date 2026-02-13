WITH ActorYears AS (
  SELECT 
    mc.PID, 
    MIN(CAST(m.year AS INTEGER)) AS min_year, 
    MAX(CAST(m.year AS INTEGER)) AS max_year
  FROM 
    M_Cast mc
  JOIN 
    Movie m ON mc.MID = m.MID
  GROUP BY 
    mc.PID
),
YearGaps AS (
  SELECT 
    ay.PID,
    m.year AS current_year,
    LAG(m.year, 1) OVER (PARTITION BY ay.PID ORDER BY m.year) AS prev_year
  FROM 
    ActorYears ay
  JOIN 
    M_Cast mc ON mc.PID = ay.PID
  JOIN 
    Movie m ON mc.MID = m.MID
  WHERE 
    CAST(m.year AS INTEGER) BETWEEN ay.min_year AND ay.max_year
),
ValidActors AS (
  SELECT 
    yg.PID
  FROM 
    YearGaps yg
  GROUP BY 
    yg.PID
  HAVING 
    MAX(COALESCE(yg.current_year - yg.prev_year, 0)) <= 3
)
SELECT 
  COUNT(DISTINCT va.PID) AS actor_count
FROM 
  ValidActors va;