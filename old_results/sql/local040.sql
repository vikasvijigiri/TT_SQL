WITH TreeCounts AS (
  SELECT t.boroname, COUNT(t.tree_id) AS tree_count
  FROM trees t
  JOIN income_trees i ON t.zipcode = i.zipcode
  WHERE i.Estimate_Median_income > 0
    AND i.Estimate_Mean_income > 0
    AND t.boroname IS NOT NULL
    AND t.boroname != ''
  GROUP BY t.boroname
),
TopBoroughs AS (
  SELECT boroname, tree_count
  FROM TreeCounts
  ORDER BY tree_count DESC
  LIMIT 3
)
SELECT tb.boroname, AVG(CAST(i.Estimate_Mean_income AS REAL)) AS average_mean_income
FROM TopBoroughs tb
JOIN trees t ON tb.boroname = t.boroname
JOIN income_trees i ON t.zipcode = i.zipcode
WHERE i.Estimate_Median_income > 0
  AND i.Estimate_Mean_income > 0
GROUP BY tb.boroname;