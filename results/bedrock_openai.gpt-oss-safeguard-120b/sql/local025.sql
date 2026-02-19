WITH over_totals AS (
    SELECT bbb.match_id,
           bbb.over_id,
           bbb.innings_no,
           MAX(bbb.bowler) AS bowler,
           SUM(COALESCE(bs.runs_scored, 0) + COALESCE(er.extra_runs, 0)) AS total_runs
    FROM ball_by_ball bbb
    LEFT JOIN batsman_scored bs ON bbb.match_id = bs.match_id
                                 AND bbb.over_id = bs.over_id
                                 AND bbb.ball_id = bs.ball_id
                                 AND bbb.innings_no = bs.innings_no
    LEFT JOIN extra_runs er ON bbb.match_id = er.match_id
                              AND bbb.over_id = er.over_id
                              AND bbb.ball_id = er.ball_id
                              AND bbb.innings_no = er.innings_no
    GROUP BY bbb.match_id, bbb.over_id, bbb.innings_no
),
max_over_per_match AS (
    SELECT match_id,
           over_id,
           innings_no,
           bowler,
           total_runs,
           ROW_NUMBER() OVER (PARTITION BY match_id ORDER BY total_runs DESC) AS rn
    FROM over_totals
)
SELECT match_id,
       over_id,
       bowler,
       total_runs,
       (SELECT AVG(total_runs) FROM max_over_per_match WHERE rn = 1) AS average_highest_over_total
FROM max_over_per_match
WHERE rn = 1;