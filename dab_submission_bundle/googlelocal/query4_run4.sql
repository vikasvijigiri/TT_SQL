SELECT bd.name AS business_name,
       COUNT(*) AS high_rating_review_count
FROM review r
JOIN business_description bd ON r.gmap_id = bd.gmap_id
WHERE r.rating >= 4.5
  AND r.time LIKE '%2019%'
  AND bd.name IS NOT NULL
  AND TRIM(bd.name) != ''
GROUP BY bd.name
ORDER BY high_rating_review_count DESC, bd.name ASC
LIMIT 3