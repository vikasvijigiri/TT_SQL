WITH StrikersOverFifty AS (
  SELECT ball_by_ball.striker, ball_by_ball.match_id, SUM(batsman_scored.runs_scored) AS total_runs
  FROM batsman_scored
  JOIN ball_by_ball ON batsman_scored.match_id = ball_by_ball.match_id
    AND batsman_scored.over_id = ball_by_ball.over_id
    AND batsman_scored.ball_id = ball_by_ball.ball_id
    AND batsman_scored.innings_no = ball_by_ball.innings_no
  GROUP BY ball_by_ball.striker, ball_by_ball.match_id
  HAVING SUM(batsman_scored.runs_scored) > 50
)
SELECT AVG(CAST(total_runs AS REAL)) AS average_runs
FROM StrikersOverFifty;