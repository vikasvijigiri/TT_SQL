SELECT ms.StyleName, 
       SUM(CASE WHEN mp.PreferenceSeq = 1 THEN 1 ELSE 0 END) AS FirstPreferenceCount, 
       SUM(CASE WHEN mp.PreferenceSeq = 2 THEN 1 ELSE 0 END) AS SecondPreferenceCount, 
       SUM(CASE WHEN mp.PreferenceSeq = 3 THEN 1 ELSE 0 END) AS ThirdPreferenceCount
FROM Musical_Preferences mp
JOIN Musical_Styles ms ON mp.StyleID = ms.StyleID
WHERE mp.PreferenceSeq IN (1, 2, 3)
GROUP BY ms.StyleName