WITH constructor_year_points AS (
  SELECT cr.constructor_id, r.year, SUM(cr.points) AS constructor_points
  FROM constructor_results cr
  JOIN races r ON cr.race_id = r.race_id
  GROUP BY cr.constructor_id, r.year
),
driver_year_points AS (
  SELECT dr.constructor_id, dr.driver_id, r.year, SUM(dr.points) AS driver_points
  FROM results dr
  JOIN races r ON dr.race_id = r.race_id
  GROUP BY dr.constructor_id, dr.driver_id, r.year
),
best_driver_points AS (
  SELECT constructor_id, year, MAX(driver_points) AS best_driver_points
  FROM driver_year_points
  GROUP BY constructor_id, year
)
SELECT con.name, cp.year, (cp.constructor_points + bd.best_driver_points) AS combined_points
FROM constructor_year_points cp
JOIN best_driver_points bd ON cp.constructor_id = bd.constructor_id AND cp.year = bd.year
JOIN constructors con ON cp.constructor_id = con.constructor_id
ORDER BY combined_points DESC
LIMIT 3;