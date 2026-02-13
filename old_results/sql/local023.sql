WITH season_matches AS (
    SELECT match_id
    FROM match
    WHERE season_id = 5
),
player_runs AS (
    SELECT b.striker AS player_id,
           SUM(bs.runs_scored) AS total_runs
    FROM ball_by_ball b
    JOIN batsman_scored bs ON b.match_id = bs.match_id
        AND b.over_id = bs.over_id
        AND b.ball_id = bs.ball_id
        AND b.innings_no = bs.innings_no
    WHERE b.match_id IN (SELECT match_id FROM season_matches)
    GROUP BY b.striker
),
player_matches AS (
    SELECT pm.player_id,
           COUNT(DISTINCT pm.match_id) AS matches_played
    FROM player_match pm
    JOIN match m ON pm.match_id = m.match_id
    WHERE m.season_id = 5
    GROUP BY pm.player_id
),
player_dismissals AS (
    SELECT wt.player_out AS player_id,
           COUNT(*) AS dismissals
    FROM wicket_taken wt
    JOIN match m ON wt.match_id = m.match_id
    WHERE m.season_id = 5
    GROUP BY wt.player_out
)
SELECT p.player_name,
       CAST(pr.total_runs AS REAL) / pm.matches_played AS avg_runs_per_match,
       CAST(pr.total_runs AS REAL) / NULLIF(pd.dismissals, 0) AS batting_average
FROM player p
JOIN player_runs pr ON p.player_id = pr.player_id
JOIN player_matches pm ON p.player_id = pm.player_id
LEFT JOIN player_dismissals pd ON p.player_id = pd.player_id
ORDER BY avg_runs_per_match DESC
LIMIT 5;