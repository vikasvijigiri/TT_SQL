SELECT ROUND(AVG(career_span), 2) AS average_career_span
FROM (
  SELECT player_id,
         ROUND((julianday(final_game) - julianday(debut)) / 365.0, 2) AS career_span
  FROM player
  WHERE debut IS NOT NULL AND final_game IS NOT NULL
);