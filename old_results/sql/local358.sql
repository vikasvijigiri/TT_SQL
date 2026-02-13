SELECT age_category,
       COUNT(*) AS user_count
FROM (
    SELECT CASE
               WHEN age BETWEEN 20 AND 29 THEN '20s'
               WHEN age BETWEEN 30 AND 39 THEN '30s'
               WHEN age BETWEEN 40 AND 49 THEN '40s'
               WHEN age BETWEEN 50 AND 59 THEN '50s'
               ELSE 'others'
           END AS age_category
    FROM (
        SELECT CAST(strftime('%Y', 'now') AS INTEGER) - CAST(strftime('%Y', birth_date) AS INTEGER) AS age
        FROM mst_users
    )
) 
GROUP BY age_category;