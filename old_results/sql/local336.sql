SELECT
  (SELECT COUNT(*) FROM retirements r WHERE r.race_id = :race_id AND r.lap BETWEEN 1 AND 5) AS retirements,
  (SELECT COUNT(*) FROM pit_stops p WHERE p.race_id = :race_id AND p.lap BETWEEN 1 AND 5) AS pit_stops,
  (SELECT COUNT(*) FROM lap_positions lp WHERE lp.race_id = :race_id AND lp.lap BETWEEN 1 AND 5 AND lp.lap_type = 'start') AS start_overtakes,
  (SELECT COUNT(*) FROM lap_positions lp2 WHERE lp2.race_id = :race_id AND lp2.lap BETWEEN 1 AND 5 AND lp2.lap_type = 'pass') AS standard_passes;