SELECT DISTINCT b.BowlerID, b.BowlerFirstName, b.BowlerLastName, bs.MatchID, bs.GameNumber, bs.HandiCapScore, t.TourneyDate, t.TourneyLocation
FROM Bowlers b
JOIN Bowler_Scores bs ON b.BowlerID = bs.BowlerID
JOIN Match_Games mg ON bs.MatchID = mg.MatchID AND bs.GameNumber = mg.GameNumber
JOIN Tourney_Matches tm ON mg.MatchID = tm.MatchID
JOIN Tournaments t ON tm.TourneyID = t.TourneyID
WHERE bs.WonGame = 1 AND bs.HandiCapScore <= 190 AND t.TourneyLocation IN ('Thunderbird Lanes', 'Totem Lanes', 'Bolero Lanes')
AND b.BowlerID IN (
  SELECT BowlerID
  FROM (
    SELECT bs1.BowlerID, t1.TourneyLocation
    FROM Bowler_Scores bs1
    JOIN Match_Games mg1 ON bs1.MatchID = mg1.MatchID AND bs1.GameNumber = mg1.GameNumber
    JOIN Tourney_Matches tm1 ON mg1.MatchID = tm1.MatchID
    JOIN Tournaments t1 ON tm1.TourneyID = t1.TourneyID
    WHERE bs1.WonGame = 1 AND bs1.HandiCapScore <= 190 AND t1.TourneyLocation IN ('Thunderbird Lanes', 'Totem Lanes', 'Bolero Lanes')
    GROUP BY bs1.BowlerID, t1.TourneyLocation
  ) AS LocationWins
  GROUP BY BowlerID
  HAVING COUNT(DISTINCT TourneyLocation) = 3
)