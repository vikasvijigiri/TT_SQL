SELECT bd.name, AVG(r.rating) AS avg_rating
FROM business_description bd
JOIN review r ON bd.gmap_id = r.gmap_id
WHERE lower(bd.description) LIKE '%massage%'
   OR lower(bd.name) LIKE '%massage%'
   OR lower(bd.description) LIKE '%therapy%'
   OR lower(bd.description) LIKE '%body treatment%'
GROUP BY bd.name
HAVING AVG(r.rating) >= 4.0
ORDER BY avg_rating DESC