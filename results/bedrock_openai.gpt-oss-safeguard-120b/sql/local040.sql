SELECT t.boroname AS borough,
       COUNT(*) AS tree_count,
       AVG(i.Estimate_Mean_income) AS average_mean_income
FROM trees t
JOIN income_trees i ON COALESCE(t.zipcode, 'UNKNOWN') = COALESCE(i.zipcode, 'UNKNOWN')
WHERE i.Estimate_Median_income > 0
  AND i.Estimate_Mean_income > 0
  AND t.boroname IS NOT NULL
  AND TRIM(t.boroname) <> ''
GROUP BY t.boroname
ORDER BY tree_count DESC
LIMIT 3