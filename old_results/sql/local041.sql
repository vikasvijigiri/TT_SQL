SELECT (CAST(COUNT(CASE WHEN health = 'Good' THEN 1 END) AS REAL) / COUNT(*)) * 100 AS percentage_good_health
FROM trees
WHERE boroname = 'Bronx';