WITH OverTotals AS (
  SELECT 
    b.match_id, 
    b.innings_no, 
    b.over_id, 
    SUM(bs.runs_scored) + SUM(COALESCE(er.extra_runs, 0)) AS total_runs
  FROM ball_by_ball b
  LEFT JOIN batsman_scored bs ON b.match_id = bs.match_id AND b.innings_no = bs.innings_no AND b.over_id = bs.over_id AND b.ball_id = bs.ball_id
  LEFT JOIN extra_runs er ON b.match_id = er.match_id AND b.innings_no = er.innings_no AND b.over_id = er.over_id AND b.ball_id = er.ball_id
  GROUP BY b.match_id, b.innings_no, b.over_id
),
MaxOverPerMatch AS (
  SELECT 
    match_id, 
    innings_no,
    over_id, 
    (SELECT bowler FROM ball_by_ball WHERE match_id = ot.match_id AND innings_no = ot.innings_no AND over_id = ot.over_id LIMIT 1) AS bowler,
    total_runs,
    ROW_NUMBER() OVER (PARTITION BY match_id ORDER BY total_runs DESC) as rn
  FROM OverTotals ot
),
FilteredMaxOver AS (
  SELECT match_id, innings_no, over_id, bowler, total_runs
  FROM MaxOverPerMatch
  WHERE rn = 1
),
AverageMaxOver AS (
  SELECT 
    AVG(CAST(total_runs AS REAL)) AS average_max_runs
  FROM FilteredMaxOver
)
SELECT * FROM AverageMaxOver;