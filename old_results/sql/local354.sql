WITH driver_season AS (
    SELECT r.driver_id,
           ra.year,
           MIN(ra.round) AS first_round,
           MAX(ra.round) AS last_round,
           COUNT(DISTINCT ra.round) AS round_cnt
    FROM results r
    JOIN races ra ON r.race_id = ra.race_id
    WHERE ra.year BETWEEN 1950 AND 1959
    GROUP BY r.driver_id, ra.year
    HAVING COUNT(DISTINCT ra.round) >= 2
), first_last AS (
    SELECT ds.driver_id,
           ds.year,
           fr.constructor_id AS first_constructor,
           lr.constructor_id AS last_constructor
    FROM driver_season ds
    JOIN results fr ON fr.driver_id = ds.driver_id
    JOIN races ra1 ON fr.race_id = ra1.race_id AND ra1.year = ds.year AND ra1.round = ds.first_round
    JOIN results lr ON lr.driver_id = ds.driver_id
    JOIN races ra2 ON lr.race_id = ra2.race_id AND ra2.year = ds.year AND ra2.round = ds.last_round
    WHERE fr.constructor_id = lr.constructor_id
)
SELECT DISTINCT d.driver_id, d.forename, d.surname
FROM first_last fl
JOIN drivers d ON d.driver_id = fl.driver_id;