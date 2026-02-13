SELECT
  category,
  MIN(duration_min) AS min_duration_minutes,
  MAX(duration_min) AS max_duration_minutes,
  SUM(COALESCE(il.UnitPrice * il.Quantity, 0)) AS total_revenue
FROM (
  SELECT
    t.TrackId,
    CAST(t.Milliseconds AS REAL) / 60000.0 AS duration_min,
    CASE
      WHEN CAST(t.Milliseconds AS REAL) / 60000.0 < 3 THEN 'short'
      WHEN CAST(t.Milliseconds AS REAL) / 60000.0 <= 5 THEN 'medium'
      ELSE 'long'
    END AS category
  FROM Track t
) AS d
LEFT JOIN InvoiceLine il ON d.TrackId = il.TrackId
GROUP BY category;