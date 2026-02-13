WITH all_teams AS (
    SELECT league_id, home_team_api_id AS team_api_id FROM Match
    UNION
    SELECT league_id, away_team_api_id FROM Match
),
wins AS (
    SELECT league_id, home_team_api_id AS team_api_id FROM Match WHERE home_team_goal > away_team_goal
    UNION ALL
    SELECT league_id, away_team_api_id FROM Match WHERE away_team_goal > home_team_goal
),
team_wins AS (
    SELECT at.league_id,
           at.team_api_id,
           COALESCE(wc.win_cnt, 0) AS win_count
    FROM all_teams at
    LEFT JOIN (
        SELECT league_id, team_api_id, COUNT(*) AS win_cnt
        FROM wins
        GROUP BY league_id, team_api_id
    ) wc ON at.league_id = wc.league_id AND at.team_api_id = wc.team_api_id
    GROUP BY at.league_id, at.team_api_id
),
ranked AS (
    SELECT tw.league_id,
           tw.team_api_id,
           tw.win_count,
           ROW_NUMBER() OVER (PARTITION BY tw.league_id ORDER BY tw.win_count ASC, tw.team_api_id) AS rn
    FROM team_wins tw
)
SELECT l.name AS league_name,
       t.team_long_name AS team_name,
       r.win_count
FROM ranked r
JOIN League l ON r.league_id = l.id
JOIN Team t ON r.team_api_id = t.team_api_id
WHERE r.rn = 1;