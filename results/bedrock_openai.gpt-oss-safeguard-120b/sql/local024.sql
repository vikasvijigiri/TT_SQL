WITH player_runs AS (
  SELECT p.player_id,
         COALESCE(SUM(s.runs_scored), 0) AS total_runs
  FROM player p
  LEFT JOIN ball_by_ball b ON p.player_id = b.striker
  LEFT JOIN batsman_scored s
    ON b.match_id = s.match_id
   AND b.over_id = s.over_id
   AND b.ball_id = s.ball_id
   AND b.innings_no = s.innings_no
  GROUP BY p.player_id
),
player_matches AS (
  SELECT player_id,
         COUNT(DISTINCT match_id) AS matches_played
  FROM player_match
  GROUP BY player_id
),
player_avg AS (
  SELECT pr.player_id,
         CAST(pr.total_runs AS REAL) / pm.matches_played AS avg_runs_per_match
  FROM player_runs pr
  JOIN player_matches pm ON pr.player_id = pm.player_id
  WHERE pm.matches_played > 0
),
country_avg AS (
  SELECT p.country_name,
         AVG(pa.avg_runs_per_match) AS country_average
  FROM player_avg pa
  JOIN player p ON pa.player_id = p.player_id
  GROUP BY p.country_name
)
SELECT country_name,
       country_average
FROM country_avg
ORDER BY country_average DESC
LIMIT 5;