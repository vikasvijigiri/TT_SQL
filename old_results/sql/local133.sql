WITH WeightedScores AS (
  SELECT 
    mp.StyleID,
    SUM(CASE 
      WHEN mp.PreferenceSeq = 1 THEN 3
      WHEN mp.PreferenceSeq = 2 THEN 2
      WHEN mp.PreferenceSeq = 3 THEN 1
      ELSE 0
    END) AS TotalWeightedScore
  FROM Musical_Preferences mp
  GROUP BY mp.StyleID
),
AverageScore AS (
  SELECT 
    AVG(ws.TotalWeightedScore) AS AvgTotalWeightedScore
  FROM WeightedScores ws
)
SELECT 
  ws.StyleID,
  ws.TotalWeightedScore,
  ABS(ws.TotalWeightedScore - avg.AvgTotalWeightedScore) AS AbsoluteDifference
FROM WeightedScores ws
CROSS JOIN AverageScore avg;