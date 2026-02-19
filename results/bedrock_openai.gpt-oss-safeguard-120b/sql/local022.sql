WITH losing_teams AS (
    SELECT match_id,
           CASE WHEN team_1 = match_winner THEN team_2 ELSE team_1 END AS losing_team_id
    FROM match
    WHERE match_winner IS NOT NULL
), player_runs AS (
    SELECT pm.player_id,
           p.player_name,
           pm.match_id,
           SUM(bs.runs_scored) AS total_runs
    FROM player_match pm
    JOIN losing_teams lt ON pm.match_id = lt.match_id AND pm.team_id = lt.losing_team_id
    JOIN ball_by_ball bbb ON pm.match_id = bbb.match_id AND pm.player_id = bbb.striker
    JOIN batsman_scored bs ON bbb.match_id = bs.match_id AND bbb.over_id = bs.over_id AND bbb.ball_id = bs.ball_id
    JOIN player p ON p.player_id = pm.player_id
    GROUP BY pm.player_id, p.player_name, pm.match_id
    HAVING SUM(bs.runs_scored) >= 100
)
SELECT DISTINCT player_name
FROM player_runs;