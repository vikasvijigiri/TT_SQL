WITH OverRuns AS (
    SELECT 
        b.match_id, 
        b.over_id, 
        b.bowler, 
        SUM(bs.runs_scored + COALESCE(er.extra_runs, 0)) AS total_runs
    FROM 
        ball_by_ball b
    LEFT JOIN 
        batsman_scored bs ON b.match_id = bs.match_id AND b.over_id = bs.over_id AND b.ball_id = bs.ball_id AND b.innings_no = bs.innings_no
    LEFT JOIN 
        extra_runs er ON b.match_id = er.match_id AND b.over_id = er.over_id AND b.ball_id = er.ball_id AND b.innings_no = er.innings_no
    GROUP BY 
        b.match_id, b.over_id, b.bowler
),
MaxOverRuns AS (
    SELECT 
        match_id, 
        MAX(total_runs) AS max_runs
    FROM 
        OverRuns
    GROUP BY 
        match_id
),
MaxOvers AS (
    SELECT 
        o.match_id, 
        o.over_id, 
        o.bowler, 
        o.total_runs
    FROM 
        OverRuns o
    JOIN 
        MaxOverRuns m ON o.match_id = m.match_id AND o.total_runs = m.max_runs
),
RankedBowlers AS (
    SELECT 
        mo.bowler, 
        mo.match_id, 
        mo.total_runs,
        RANK() OVER (ORDER BY mo.total_runs DESC) as rank
    FROM 
        MaxOvers mo
)
SELECT 
    p.player_name, 
    rb.match_id, 
    rb.total_runs
FROM 
    RankedBowlers rb
JOIN 
    player p ON rb.bowler = p.player_id
WHERE 
    rb.rank <= 3;