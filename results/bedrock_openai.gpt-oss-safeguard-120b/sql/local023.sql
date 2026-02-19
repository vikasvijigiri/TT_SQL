WITH runs AS (
    SELECT b.striker AS player_id,
           SUM(bs.runs_scored) AS total_runs
    FROM match m
    JOIN ball_by_ball b ON b.match_id = m.match_id
    JOIN batsman_scored bs ON bs.match_id = b.match_id
        AND bs.over_id = b.over_id
        AND bs.ball_id = b.ball_id
        AND bs.innings_no = b.innings_no
    WHERE m.season_id = 5
    GROUP BY b.striker
), matches AS (
    SELECT pm.player_id,
           COUNT(DISTINCT pm.match_id) AS match_count
    FROM match m
    JOIN player_match pm ON pm.match_id = m.match_id
    WHERE m.season_id = 5
    GROUP BY pm.player_id
), dismissals AS (
    SELECT wt.player_out AS player_id,
           COUNT(*) AS dismissals
    FROM match m
    JOIN wicket_taken wt ON wt.match_id = m.match_id
    WHERE m.season_id = 5
    GROUP BY wt.player_out
)
SELECT p.player_name,
       CASE WHEN d.dismissals > 0 THEN (r.total_runs * 1.0) / d.dismissals END AS batting_average
FROM runs r
JOIN matches m ON m.player_id = r.player_id
JOIN player p ON p.player_id = r.player_id
LEFT JOIN dismissals d ON d.player_id = r.player_id
ORDER BY (r.total_runs * 1.0) / m.match_count DESC
LIMIT 5;