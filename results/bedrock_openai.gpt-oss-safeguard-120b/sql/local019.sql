WITH nxt_matches AS (
    SELECT m.id, m.winner_id, m.loser_id, m.duration
    FROM Matches m
    JOIN Belts b ON m.title_id = b.id
    WHERE LOWER(b.name) LIKE '%nxt%title%'
      AND COALESCE(m.title_change, 0) = 0
      AND m.duration IS NOT NULL
)
SELECT w1.name AS wrestler1,
       w2.name AS wrestler2
FROM nxt_matches nm
JOIN Wrestlers w1 ON nm.winner_id = w1.id
JOIN Wrestlers w2 ON nm.loser_id = w2.id
WHERE nm.duration = (SELECT MIN(duration) FROM nxt_matches);