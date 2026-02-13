SELECT p.player_name, 
       (CAST(SUM(bs.runs_scored + COALESCE(er.extra_runs, 0)) AS REAL) / CAST(COUNT(wt.player_out) AS REAL)) AS bowling_average
FROM ball_by_ball AS bb
JOIN batsman_scored AS bs ON bb.match_id = bs.match_id AND bb.over_id = bs.over_id AND bb.ball_id = bs.ball_id AND bb.innings_no = bs.innings_no
LEFT JOIN extra_runs AS er ON bb.match_id = er.match_id AND bb.over_id = er.over_id AND bb.ball_id = er.ball_id AND bb.innings_no = er.innings_no
LEFT JOIN wicket_taken AS wt ON bb.match_id = wt.match_id AND bb.over_id = wt.over_id AND bb.ball_id = wt.ball_id AND bb.innings_no = wt.innings_no
JOIN player AS p ON bb.bowler = p.player_id
WHERE er.extra_type IS NULL OR er.extra_type NOT IN ('wides', 'noballs')
GROUP BY bb.bowler
HAVING COUNT(wt.player_out) > 0
ORDER BY bowling_average ASC
LIMIT 1;