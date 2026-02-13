WITH driver_year AS (
  SELECT ra.year, r.driver_id, SUM(r.points) AS driver_points
  FROM results r
  JOIN races ra ON r.race_id = ra.race_id
  GROUP BY ra.year, r.driver_id
), driver_max AS (
  SELECT year, MAX(driver_points) AS max_driver_points
  FROM driver_year
  GROUP BY year
), constructor_year AS (
  SELECT ra.year, r.constructor_id, SUM(r.points) AS constructor_points
  FROM results r
  JOIN races ra ON r.race_id = ra.race_id
  GROUP BY ra.year, r.constructor_id
), constructor_max AS (
  SELECT year, MAX(constructor_points) AS max_constructor_points
  FROM constructor_year
  GROUP BY year
), combined AS (
  SELECT d.year,
         d.max_driver_points + c.max_constructor_points AS total
  FROM driver_max d
  JOIN constructor_max c ON d.year = c.year
)
SELECT year, total
FROM combined
ORDER BY total ASC, year ASC
LIMIT 3;