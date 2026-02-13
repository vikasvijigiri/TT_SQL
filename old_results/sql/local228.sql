WITH batsman_runs AS (
  SELECT m.season_id,
         b.striker AS player_id,
         SUM(bs.runs_scored) AS total_runs
  FROM batsman_scored bs
  JOIN ball_by_ball b
    ON bs.match_id = b.match_id
   AND bs.over_id = b.over_id
   AND bs.ball_id = b.ball_id
  JOIN "match" m
    ON bs.match_id = m.match_id
  GROUP BY m.season_id, b.striker
),
bat_ranked AS (
  SELECT season_id,
         player_id,
         total_runs,
         ROW_NUMBER() OVER (PARTITION BY season_id ORDER BY total_runs DESC, player_id ASC) AS rn
  FROM batsman_runs
),
top_batsmen AS (
  SELECT season_id,
         player_id AS batsman_id,
         total_runs,
         rn
  FROM bat_ranked
  WHERE rn <= 3
),
bowler_wickets AS (
  SELECT m.season_id,
         b.bowler AS player_id,
         COUNT(*) AS total_wickets
  FROM wicket_taken w
  JOIN ball_by_ball b
    ON w.match_id = b.match_id
   AND w.over_id = b.over_id
   AND w.ball_id = b.ball_id
  JOIN "match" m
    ON w.match_id = m.match_id
  WHERE w.kind_out NOT IN ('run out', 'hit wicket', 'retired hurt')
  GROUP BY m.season_id, b.bowler
),
bowler_ranked AS (
  SELECT season_id,
         player_id,
         total_wickets,
         ROW_NUMBER() OVER (PARTITION BY season_id ORDER BY total_wickets DESC, player_id ASC) AS rn
  FROM bowler_wickets
),
top_bowlers AS (
  SELECT season_id,
         player_id AS bowler_id,
         total_wickets,
         rn
  FROM bowler_ranked
  WHERE rn <= 3
)
SELECT b.season_id,
       b.rn AS position,
       b.batsman_id,
       b.total_runs,
       bw.bowler_id,
       bw.total_wickets
FROM top_batsmen b
JOIN top_bowlers bw
  ON b.season_id = bw.season_id
 AND b.rn = bw.rn
ORDER BY b.season_id, b.rn;