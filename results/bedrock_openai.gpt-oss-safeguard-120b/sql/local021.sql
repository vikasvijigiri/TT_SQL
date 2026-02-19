WITH match_runs AS (
    SELECT b.striker AS player_id,
           b.match_id,
           SUM(CAST(bs.runs_scored AS INTEGER)) AS runs_in_match
    FROM ball_by_ball b
    JOIN batsman_scored bs ON b.match_id = bs.match_id
                         AND b.over_id = bs.over_id
                         AND b.ball_id = bs.ball_id
                         AND b.innings_no = bs.innings_no
    GROUP BY b.striker, b.match_id
),
players_with_50 AS (
    SELECT DISTINCT player_id
    FROM match_runs
    WHERE runs_in_match > 50
),
total_runs_per_player AS (
    SELECT mr.player_id,
           SUM(mr.runs_in_match) AS total_runs
    FROM match_runs mr
    WHERE mr.player_id IN (SELECT player_id FROM players_with_50)
    GROUP BY mr.player_id
)
SELECT AVG(total_runs) AS average_total_runs
FROM total_runs_per_player;