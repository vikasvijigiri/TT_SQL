WITH driver_years AS (
    SELECT DISTINCT r.driver_id, ra.year
    FROM results r
    JOIN races ra ON r.race_id = ra.race_id
),
all_driver_races AS (
    SELECT dy.driver_id,
           dy.year,
           ra.round,
           ra.race_id
    FROM driver_years dy
    JOIN races ra ON ra.year = dy.year
),
missed_flags AS (
    SELECT adr.driver_id,
           adr.year,
           adr.round,
           adr.race_id,
           CASE WHEN res.result_id IS NULL THEN 1 ELSE 0 END AS missed,
           res.constructor_id
    FROM all_driver_races adr
    LEFT JOIN results res ON res.race_id = adr.race_id AND res.driver_id = adr.driver_id
),
missed_groups AS (
    SELECT mf.*, 
           SUM(CASE WHEN missed = 0 THEN 1 ELSE 0 END) OVER (PARTITION BY driver_id, year ORDER BY round) AS grp
    FROM missed_flags mf
),
contiguous_blocks AS (
    SELECT driver_id,
           year,
           grp,
           MIN(round) AS first_missed,
           MAX(round) AS last_missed,
           COUNT(*) AS missed_cnt
    FROM missed_groups
    WHERE missed = 1
    GROUP BY driver_id, year, grp
    HAVING missed_cnt < 3
),
qualified_blocks AS (
    SELECT cb.driver_id,
           cb.year,
           cb.first_missed,
           cb.last_missed,
           prev_res.constructor_id AS prev_constructor,
           next_res.constructor_id AS next_constructor
    FROM contiguous_blocks cb
    LEFT JOIN races prev_race ON prev_race.year = cb.year AND prev_race.round = cb.first_missed - 1
    LEFT JOIN results prev_res ON prev_res.race_id = prev_race.race_id AND prev_res.driver_id = cb.driver_id
    LEFT JOIN races next_race ON next_race.year = cb.year AND next_race.round = cb.last_missed + 1
    LEFT JOIN results next_res ON next_res.race_id = next_race.race_id AND next_res.driver_id = cb.driver_id
    WHERE prev_res.constructor_id IS NOT NULL
      AND next_res.constructor_id IS NOT NULL
      AND prev_res.constructor_id <> next_res.constructor_id
)
SELECT AVG(first_missed) AS avg_first_missed_round,
       AVG(last_missed) AS avg_last_missed_round
FROM qualified_blocks;