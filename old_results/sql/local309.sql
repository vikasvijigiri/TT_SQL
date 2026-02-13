WITH driver_totals AS (
    SELECT r.year, res.driver_id, SUM(res.points) AS total_points
    FROM results res
    JOIN races r ON res.race_id = r.race_id
    GROUP BY r.year, res.driver_id
), driver_ranked AS (
    SELECT year, driver_id, total_points,
           ROW_NUMBER() OVER (PARTITION BY year ORDER BY total_points DESC) AS rn
    FROM driver_totals
), driver_best AS (
    SELECT year, driver_id, total_points
    FROM driver_ranked
    WHERE rn = 1
), constructor_totals AS (
    SELECT r.year, res.constructor_id, SUM(res.points) AS total_points
    FROM results res
    JOIN races r ON res.race_id = r.race_id
    GROUP BY r.year, res.constructor_id
), constructor_ranked AS (
    SELECT year, constructor_id, total_points,
           ROW_NUMBER() OVER (PARTITION BY year ORDER BY total_points DESC) AS rn
    FROM constructor_totals
), constructor_best AS (
    SELECT year, constructor_id, total_points
    FROM constructor_ranked
    WHERE rn = 1
)
SELECT d.year,
       de.full_name AS driver_full_name,
       ct.name AS constructor_name
FROM driver_best d
JOIN drivers_ext de ON d.driver_id = de.driver_id
JOIN constructor_best c ON d.year = c.year
JOIN constructors ct ON c.constructor_id = ct.constructor_id
ORDER BY d.year;