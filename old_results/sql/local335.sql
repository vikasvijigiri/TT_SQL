WITH season_constructor_points AS (
    SELECT r.year,
           res.constructor_id,
           SUM(res.points) AS total_points
    FROM results res
    JOIN races r ON res.race_id = r.race_id
    WHERE r.year >= 2001
      AND res.points > 0
    GROUP BY r.year, res.constructor_id
),
min_points_per_year AS (
    SELECT year,
           MIN(total_points) AS min_points
    FROM season_constructor_points
    GROUP BY year
),
constructors_with_min AS (
    SELECT scp.year,
           scp.constructor_id
    FROM season_constructor_points scp
    JOIN min_points_per_year mp
      ON scp.year = mp.year
     AND scp.total_points = mp.min_points
)
SELECT c.name,
       COUNT(DISTINCT cwm.year) AS season_count
FROM constructors_with_min cwm
JOIN constructors c ON cwm.constructor_id = c.constructor_id
GROUP BY cwm.constructor_id
ORDER BY season_count DESC, c.name
LIMIT 5;