WITH team_season_goals AS (
    SELECT team_api_id, season, SUM(goals) AS total_goals
    FROM (
        SELECT home_team_api_id AS team_api_id, season, home_team_goal AS goals FROM Match
        UNION ALL
        SELECT away_team_api_id AS team_api_id, season, away_team_goal AS goals FROM Match
    )
    GROUP BY team_api_id, season
),
team_max_goals AS (
    SELECT team_api_id, MAX(total_goals) AS max_goals
    FROM team_season_goals
    GROUP BY team_api_id
),
ordered AS (
    SELECT max_goals,
           ROW_NUMBER() OVER (ORDER BY max_goals) AS rn,
           COUNT(*) OVER () AS cnt
    FROM team_max_goals
)
SELECT CASE
         WHEN cnt % 2 = 1 THEN (
             SELECT max_goals FROM ordered WHERE rn = (cnt + 1) / 2
         )
         ELSE (
             (SELECT max_goals FROM ordered WHERE rn = cnt / 2) +
             (SELECT max_goals FROM ordered WHERE rn = cnt / 2 + 1)
         ) / 2.0
       END AS median_max_goals
FROM ordered
LIMIT 1;