WITH base AS (
    SELECT player_id, debut, final_game
    FROM player
    WHERE debut IS NOT NULL AND final_game IS NOT NULL
), calc AS (
    SELECT player_id,
           ROUND((julianday(final_game) - julianday(debut)) / 365.0, 2) AS career_span_years
    FROM base
)
SELECT ROUND(AVG(career_span_years), 2) AS average_career_span
FROM calc;