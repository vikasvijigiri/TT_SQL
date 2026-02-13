WITH all_players AS (
    SELECT m.id AS match_id, m.home_player_1 AS player_id, 'home' AS side FROM Match m WHERE m.home_player_1 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_2, 'home' FROM Match m WHERE m.home_player_2 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_3, 'home' FROM Match m WHERE m.home_player_3 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_4, 'home' FROM Match m WHERE m.home_player_4 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_5, 'home' FROM Match m WHERE m.home_player_5 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_6, 'home' FROM Match m WHERE m.home_player_6 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_7, 'home' FROM Match m WHERE m.home_player_7 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_8, 'home' FROM Match m WHERE m.home_player_8 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_9, 'home' FROM Match m WHERE m.home_player_9 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_10, 'home' FROM Match m WHERE m.home_player_10 IS NOT NULL
    UNION ALL SELECT m.id, m.home_player_11, 'home' FROM Match m WHERE m.home_player_11 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_1, 'away' FROM Match m WHERE m.away_player_1 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_2, 'away' FROM Match m WHERE m.away_player_2 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_3, 'away' FROM Match m WHERE m.away_player_3 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_4, 'away' FROM Match m WHERE m.away_player_4 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_5, 'away' FROM Match m WHERE m.away_player_5 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_6, 'away' FROM Match m WHERE m.away_player_6 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_7, 'away' FROM Match m WHERE m.away_player_7 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_8, 'away' FROM Match m WHERE m.away_player_8 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_9, 'away' FROM Match m WHERE m.away_player_9 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_10, 'away' FROM Match m WHERE m.away_player_10 IS NOT NULL
    UNION ALL SELECT m.id, m.away_player_11, 'away' FROM Match m WHERE m.away_player_11 IS NOT NULL
), results AS (
    SELECT ap.player_id,
           CASE 
               WHEN m.home_team_goal > m.away_team_goal AND ap.side = 'home' THEN 'win'
               WHEN m.home_team_goal < m.away_team_goal AND ap.side = 'home' THEN 'loss'
               WHEN m.home_team_goal < m.away_team_goal AND ap.side = 'away' THEN 'win'
               WHEN m.home_team_goal > m.away_team_goal AND ap.side = 'away' THEN 'loss'
           END AS outcome
    FROM all_players ap
    JOIN Match m ON m.id = ap.match_id
    WHERE m.home_team_goal != m.away_team_goal
), agg AS (
    SELECT r.player_id,
           SUM(CASE WHEN r.outcome = 'win' THEN 1 ELSE 0 END) AS win_count,
           SUM(CASE WHEN r.outcome = 'loss' THEN 1 ELSE 0 END) AS loss_count
    FROM results r
    GROUP BY r.player_id
), max_win AS (
    SELECT a.player_id, a.win_count
    FROM agg a
    ORDER BY a.win_count DESC
    LIMIT 1
), max_loss AS (
    SELECT a.player_id, a.loss_count
    FROM agg a
    ORDER BY a.loss_count DESC
    LIMIT 1
)
SELECT p.player_name, 'win' AS type, mw.win_count AS count
FROM max_win mw
JOIN Player p ON p.player_api_id = mw.player_id
UNION ALL
SELECT p.player_name, 'loss' AS type, ml.loss_count AS count
FROM max_loss ml
JOIN Player p ON p.player_api_id = ml.player_id;