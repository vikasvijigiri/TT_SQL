WITH legal_deliveries AS (
    SELECT b.match_id, b.over_id, b.ball_id, b.innings_no, b.bowler
    FROM ball_by_ball b
    LEFT JOIN extra_runs e
        ON b.match_id = e.match_id
        AND b.over_id = e.over_id
        AND b.ball_id = e.ball_id
        AND b.innings_no = e.innings_no
    WHERE e.extra_type NOT IN ('wide', 'no-ball') OR e.extra_type IS NULL
),
runs AS (
    SELECT ld.bowler,
           ld.match_id,
           SUM(COALESCE(bs.runs_scored, 0)) AS runs_conceded
    FROM legal_deliveries ld
    LEFT JOIN batsman_scored bs
        ON ld.match_id = bs.match_id
        AND ld.over_id = bs.over_id
        AND ld.ball_id = bs.ball_id
        AND ld.innings_no = bs.innings_no
    GROUP BY ld.bowler, ld.match_id
),
balls AS (
    SELECT bowler,
           match_id,
           COUNT(*) AS balls_bowled
    FROM legal_deliveries
    GROUP BY bowler, match_id
),
wickets AS (
    SELECT b.bowler,
           wt.match_id,
           COUNT(*) AS wickets
    FROM wicket_taken wt
    JOIN ball_by_ball b
        ON wt.match_id = b.match_id
        AND wt.over_id = b.over_id
        AND wt.ball_id = b.ball_id
        AND wt.innings_no = b.innings_no
    WHERE wt.kind_out != 'run out'
    GROUP BY b.bowler, wt.match_id
),
bowler_match_stats AS (
    SELECT COALESCE(b.bowler, w.bowler) AS bowler,
           COALESCE(b.match_id, w.match_id) AS match_id,
           COALESCE(balls_bowled, 0) AS balls_bowled,
           COALESCE(r.runs_conceded, 0) AS runs_conceded,
           COALESCE(w.wickets, 0) AS wickets
    FROM balls b
    LEFT JOIN runs r ON b.bowler = r.bowler AND b.match_id = r.match_id
    LEFT JOIN wickets w ON b.bowler = w.bowler AND b.match_id = w.match_id
),
total_stats AS (
    SELECT bowler,
           SUM(wickets) AS total_wickets,
           SUM(runs_conceded) AS total_runs,
           SUM(balls_bowled) AS total_balls
    FROM bowler_match_stats
    GROUP BY bowler
),
best_perf AS (
    SELECT bowler,
           wickets || '-' || runs_conceded AS best_bowling
    FROM (
        SELECT bm.bowler,
               bm.wickets,
               bm.runs_conceded,
               ROW_NUMBER() OVER (PARTITION BY bm.bowler ORDER BY bm.wickets DESC, bm.runs_conceded ASC) AS rn
        FROM bowler_match_stats bm
    ) sub
    WHERE rn = 1
)
SELECT p.player_id,
       p.player_name,
       ts.total_wickets,
       CASE WHEN ts.total_balls = 0 THEN 0 ELSE CAST(ts.total_runs AS REAL) * 6 / ts.total_balls END AS economy_rate,
       CASE WHEN ts.total_wickets = 0 THEN NULL ELSE CAST(ts.total_balls AS REAL) / ts.total_wickets END AS strike_rate,
       bp.best_bowling
FROM total_stats ts
JOIN player p ON ts.bowler = p.player_id
LEFT JOIN best_perf bp ON ts.bowler = bp.bowler
ORDER BY p.player_name;