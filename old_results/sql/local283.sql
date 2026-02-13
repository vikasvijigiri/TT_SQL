WITH team_points AS (
  SELECT m.season,
         m.league_id,
         m.country_id,
         m.home_team_api_id AS team_api_id,
         CASE
           WHEN m.home_team_goal > m.away_team_goal THEN 3
           WHEN m.home_team_goal = m.away_team_goal THEN 1
           ELSE 0
         END AS points
  FROM Match m
  UNION ALL
  SELECT m.season,
         m.league_id,
         m.country_id,
         m.away_team_api_id AS team_api_id,
         CASE
           WHEN m.away_team_goal > m.home_team_goal THEN 3
           WHEN m.away_team_goal = m.home_team_goal THEN 1
           ELSE 0
         END AS points
  FROM Match m
),
agg_points AS (
  SELECT season,
         league_id,
         country_id,
         team_api_id,
         SUM(points) AS total_points
  FROM team_points
  GROUP BY season, league_id, country_id, team_api_id
),
max_points AS (
  SELECT season,
         league_id,
         country_id,
         MAX(total_points) AS max_points
  FROM agg_points
  GROUP BY season, league_id, country_id
)
SELECT t.team_long_name AS team_name,
       l.name AS league,
       c.name AS country,
       ap.season,
       ap.total_points
FROM agg_points ap
JOIN max_points mp ON ap.season = mp.season
                    AND ap.league_id = mp.league_id
                    AND ap.country_id = mp.country_id
                    AND ap.total_points = mp.max_points
JOIN Team t ON t.team_api_id = ap.team_api_id
JOIN League l ON l.id = ap.league_id
JOIN Country c ON c.id = ap.country_id
ORDER BY ap.season, l.name, c.name;