WITH filtered AS (
    SELECT race_id, driver_id, lap, position
    FROM lap_positions
    WHERE lap_type NOT IN ('pit', 'retirement', 'start')
      AND lap > 1
),
pos_prev AS (
    SELECT race_id,
           driver_id,
           lap,
           position,
           LAG(position) OVER (PARTITION BY race_id, driver_id ORDER BY lap) AS prev_position
    FROM filtered
),
overtake_events AS (
    SELECT p1.driver_id AS driver_id,
           CASE WHEN p1.prev_position > p2.prev_position AND p1.position < p2.position THEN 1 ELSE 0 END AS overtook_flag,
           CASE WHEN p1.prev_position < p2.prev_position AND p1.position > p2.position THEN 1 ELSE 0 END AS overtaken_flag
    FROM pos_prev p1
    JOIN pos_prev p2
      ON p1.race_id = p2.race_id
     AND p1.lap = p2.lap
     AND p1.driver_id <> p2.driver_id
    WHERE p1.prev_position IS NOT NULL
      AND p2.prev_position IS NOT NULL
),
driver_counts AS (
    SELECT driver_id,
           SUM(overtook_flag) AS overtook_cnt,
           SUM(overtaken_flag) AS overtaken_cnt
    FROM overtake_events
    GROUP BY driver_id
)
SELECT d.full_name
FROM driver_counts dc
JOIN drivers_ext d ON d.driver_id = dc.driver_id
WHERE dc.overtaken_cnt > dc.overtook_cnt;