WITH EntertainerStyles AS (
  SELECT EntertainerID
  FROM Entertainer_Styles
  GROUP BY EntertainerID
  HAVING COUNT(StyleID) <= 3
),
CustomerPreferences AS (
  SELECT CustomerID
  FROM Musical_Preferences
  GROUP BY CustomerID
  HAVING COUNT(StyleID) <= 3
),
MatchingPairs AS (
  SELECT es1.EntertainerID, mp1.CustomerID
  FROM Entertainer_Styles es1
  JOIN Entertainer_Styles es2 ON es1.EntertainerID = es2.EntertainerID AND es1.StyleID != es2.StyleID
  JOIN Musical_Preferences mp1 ON es1.StyleID = mp1.StyleID
  JOIN Musical_Preferences mp2 ON es2.StyleID = mp2.StyleID AND mp1.CustomerID = mp2.CustomerID
  WHERE es1.EntertainerID IN (SELECT EntertainerID FROM EntertainerStyles)
    AND mp1.CustomerID IN (SELECT CustomerID FROM CustomerPreferences)
    AND ((mp1.PreferenceSeq = 1 AND mp2.PreferenceSeq = 2) OR (mp1.PreferenceSeq = 2 AND mp2.PreferenceSeq = 1))
  GROUP BY es1.EntertainerID, mp1.CustomerID
)
SELECT e.EntStageName, c.CustLastName
FROM MatchingPairs mp
JOIN Entertainers e ON mp.EntertainerID = e.EntertainerID
JOIN Customers c ON mp.CustomerID = c.CustomerID;