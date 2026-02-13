WITH player_runs AS (
  SELECT b.match_id,
         b.striker AS player_id,
         SUM(COALESCE(s.runs_scored, 0)) AS total_runs
  FROM ball_by_ball b
  JOIN batsman_scored s
    ON b.match_id = s.match_id
   AND b.over_id = s.over_id
   AND b.ball_id = s.ball_id
   AND b.innings_no = s.innings_no
  GROUP BY b.match_id, b.striker
)
SELECT DISTINCT p.player_name
FROM player_runs pr
JOIN player_match pm ON pr.match_id = pm.match_id AND pr.player_id = pm.player_id
JOIN "match" m ON pr.match_id = m.match_id
JOIN player p ON pr.player_id = p.player_id
WHERE pr.total_runs >= 100
  AND pm.team_id <> m.match_winner;