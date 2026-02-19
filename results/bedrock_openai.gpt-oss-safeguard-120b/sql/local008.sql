WITH player_totals AS (
    SELECT p.name_given,
           SUM(b.g) AS total_games,
           SUM(b.r) AS total_runs,
           SUM(b.h) AS total_hits,
           SUM(b.hr) AS total_hr
    FROM player p
    JOIN batting b ON p.player_id = b.player_id
    GROUP BY p.player_id, p.name_given
),
max_vals AS (
    SELECT MAX(total_games) AS max_games,
           MAX(total_runs) AS max_runs,
           MAX(total_hits) AS max_hits,
           MAX(total_hr) AS max_hr
    FROM player_totals
)
SELECT pt.name_given, 'Games Played' AS metric, pt.total_games AS value
FROM player_totals pt, max_vals mv
WHERE pt.total_games = mv.max_games
UNION ALL
SELECT pt.name_given, 'Runs' AS metric, pt.total_runs AS value
FROM player_totals pt, max_vals mv
WHERE pt.total_runs = mv.max_runs
UNION ALL
SELECT pt.name_given, 'Hits' AS metric, pt.total_hits AS value
FROM player_totals pt, max_vals mv
WHERE pt.total_hits = mv.max_hits
UNION ALL
SELECT pt.name_given, 'Home Runs' AS metric, pt.total_hr AS value
FROM player_totals pt, max_vals mv
WHERE pt.total_hr = mv.max_hr
ORDER BY metric;