SELECT ROUND(CAST(SUM(CASE WHEN LOWER(health) = 'good' THEN 1 ELSE 0 END) AS REAL) / COUNT(*) * 100, 2) AS good_percentage
FROM trees
WHERE LOWER(boroname) = 'bronx';