WITH over_runs AS (
    SELECT
        b.match_id,
        b.over_id,
        b.bowler,
        SUM(COALESCE(bs.runs_scored, 0) + COALESCE(e.extra_runs, 0)) AS total_runs
    FROM ball_by_ball b
    LEFT JOIN batsman_scored bs
        ON b.match_id = bs.match_id
        AND b.over_id = bs.over_id
        AND b.ball_id = bs.ball_id
        AND b.innings_no = bs.innings_no
    LEFT JOIN extra_runs e
        ON b.match_id = e.match_id
        AND b.over_id = e.over_id
        AND b.ball_id = e.ball_id
        AND b.innings_no = e.innings_no
    GROUP BY b.match_id, b.over_id, b.bowler
),
match_max_over AS (
    SELECT
        match_id,
        MAX(total_runs) AS max_over_runs
    FROM over_runs
    GROUP BY match_id
),
selected_overs AS (
    SELECT
        o.match_id,
        o.over_id,
        o.bowler,
        o.total_runs
    FROM over_runs o
    JOIN match_max_over m
        ON o.match_id = m.match_id
        AND o.total_runs = m.max_over_runs
),
best_per_bowler AS (
    SELECT
        bowler,
        MAX(total_runs) AS best_runs
    FROM selected_overs
    GROUP BY bowler
),
bowler_match AS (
    SELECT
        s.bowler,
        s.match_id,
        s.total_runs AS best_runs
    FROM selected_overs s
    JOIN best_per_bowler b
        ON s.bowler = b.bowler
        AND s.total_runs = b.best_runs
),
ranked_bowlers AS (
    SELECT
        bm.bowler,
        bm.match_id,
        bm.best_runs,
        ROW_NUMBER() OVER (ORDER BY bm.best_runs DESC) AS rn
    FROM bowler_match bm
)
SELECT
    p.player_name AS bowler_name,
    r.match_id,
    r.best_runs AS runs_conceded_in_over
FROM ranked_bowlers r
JOIN player p ON p.player_id = r.bowler
WHERE r.rn <= 3;