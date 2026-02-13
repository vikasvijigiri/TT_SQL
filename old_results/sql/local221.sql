SELECT t.team_long_name, w.wins
FROM (
    SELECT winner_id, COUNT(*) AS wins
    FROM (
        SELECT home_team_api_id AS winner_id FROM Match WHERE home_team_goal > away_team_goal
        UNION ALL
        SELECT away_team_api_id AS winner_id FROM Match WHERE away_team_goal > home_team_goal
    ) AS winners
    GROUP BY winner_id
) w
JOIN Team t ON t.team_api_id = w.winner_id
ORDER BY w.wins DESC
LIMIT 10