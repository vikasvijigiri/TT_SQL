WITH bowler_stats AS (
  SELECT
    b.bowler AS bowler_id,
    SUM(COALESCE(bs.runs_scored, 0) + COALESCE(e.extra_runs, 0)) AS total_runs,
    COUNT(wt.ball_id) AS wickets
  FROM ball_by_ball b
  LEFT JOIN batsman_scored bs ON b.match_id = bs.match_id AND b.over_id = bs.over_id AND b.ball_id = bs.ball_id
  LEFT JOIN extra_runs e ON b.match_id = e.match_id AND b.over_id = e.over_id AND b.ball_id = e.ball_id
  LEFT JOIN wicket_taken wt ON b.match_id = wt.match_id AND b.over_id = wt.over_id AND b.ball_id = wt.ball_id
  GROUP BY b.bowler
)
SELECT p.player_name
FROM bowler_stats bs
JOIN player p ON bs.bowler_id = p.player_id
WHERE bs.wickets > 0
ORDER BY CAST(bs.total_runs AS REAL) / bs.wickets ASC
LIMIT 1;