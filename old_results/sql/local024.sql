WITH PlayerAverageRuns AS (
    SELECT 
        pm.player_id,
        SUM(bs.runs_scored) AS total_runs,
        COUNT(DISTINCT pm.match_id) AS matches_played,
        CAST(SUM(bs.runs_scored) AS REAL) / COUNT(DISTINCT pm.match_id) AS average_runs_per_match
    FROM player_match pm
    JOIN batsman_scored bs ON pm.match_id = bs.match_id AND pm.player_id = bs.striker
    GROUP BY pm.player_id
    HAVING COUNT(DISTINCT pm.match_id) > 0
),
CountryAverageRuns AS (
    SELECT 
        p.country_name,
        AVG(par.average_runs_per_match) AS country_average_runs
    FROM PlayerAverageRuns par
    JOIN player p ON par.player_id = p.player_id
    GROUP BY p.country_name
)
SELECT 
    country_name,
    country_average_runs
FROM CountryAverageRuns
ORDER BY country_average_runs DESC
LIMIT 5;