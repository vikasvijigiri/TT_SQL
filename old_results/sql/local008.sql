WITH MaxGames AS (
    SELECT player_id, g AS max_games
    FROM batting
    WHERE g = (SELECT MAX(g) FROM batting)
),
MaxRuns AS (
    SELECT player_id, r AS max_runs
    FROM batting
    WHERE r = (SELECT MAX(r) FROM batting)
),
MaxHits AS (
    SELECT player_id, h AS max_hits
    FROM batting
    WHERE h = (SELECT MAX(h) FROM batting)
),
MaxHomeRuns AS (
    SELECT player_id, hr AS max_home_runs
    FROM batting
    WHERE hr = (SELECT MAX(hr) FROM batting)
)
SELECT p.name_given AS player_name, mg.max_games AS score_value, 'Games Played' AS category
FROM MaxGames mg
JOIN player p ON mg.player_id = p.player_id
UNION ALL
SELECT p.name_given AS player_name, mr.max_runs AS score_value, 'Runs' AS category
FROM MaxRuns mr
JOIN player p ON mr.player_id = p.player_id
UNION ALL
SELECT p.name_given AS player_name, mh.max_hits AS score_value, 'Hits' AS category
FROM MaxHits mh
JOIN player p ON mh.player_id = p.player_id
UNION ALL
SELECT p.name_given AS player_name, mhr.max_home_runs AS score_value, 'Home Runs' AS category
FROM MaxHomeRuns mhr
JOIN player p ON mhr.player_id = p.player_id;