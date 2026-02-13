WITH pair_runs AS (
  SELECT
    b.match_id,
    CASE WHEN b.striker < b.non_striker THEN b.striker ELSE b.non_striker END AS player_a,
    CASE WHEN b.striker < b.non_striker THEN b.non_striker ELSE b.striker END AS player_b,
    b.striker,
    s.runs_scored
  FROM ball_by_ball b
  JOIN batsman_scored s
    ON b.match_id = s.match_id
   AND b.over_id = s.over_id
   AND b.ball_id = s.ball_id
   AND b.innings_no = s.innings_no
),
pair_agg AS (
  SELECT
    match_id,
    player_a,
    player_b,
    SUM(runs_scored) AS total_runs,
    SUM(CASE WHEN striker = player_a THEN runs_scored ELSE 0 END) AS score_a,
    SUM(CASE WHEN striker = player_b THEN runs_scored ELSE 0 END) AS score_b
  FROM pair_runs
  GROUP BY match_id, player_a, player_b
),
max_runs AS (
  SELECT match_id, MAX(total_runs) AS max_total
  FROM pair_agg
  GROUP BY match_id
)
SELECT
  pa.match_id,
  CASE
    WHEN pa.score_a > pa.score_b OR (pa.score_a = pa.score_b AND pa.player_a > pa.player_b) THEN pa.player_a
    ELSE pa.player_b
  END AS player1_id,
  CASE
    WHEN pa.score_a > pa.score_b OR (pa.score_a = pa.score_b AND pa.player_a > pa.player_b) THEN pa.score_a
    ELSE pa.score_b
  END AS player1_score,
  CASE
    WHEN pa.score_a > pa.score_b OR (pa.score_a = pa.score_b AND pa.player_a > pa.player_b) THEN pa.player_b
    ELSE pa.player_a
  END AS player2_id,
  CASE
    WHEN pa.score_a > pa.score_b OR (pa.score_a = pa.score_b AND pa.player_a > pa.player_b) THEN pa.score_b
    ELSE pa.score_a
  END AS player2_score,
  pa.total_runs
FROM pair_agg pa
JOIN max_runs mr ON pa.match_id = mr.match_id AND pa.total_runs = mr.max_total
ORDER BY pa.match_id;