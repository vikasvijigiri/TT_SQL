WITH MostCommonCategory2021 AS (
    SELECT c.pcf_violation_category, COUNT(*) AS incident_count
    FROM collisions c
    JOIN case_ids ci ON c.case_id = ci.case_id
    WHERE ci.db_year = 2021
    GROUP BY c.pcf_violation_category
    ORDER BY incident_count DESC
    LIMIT 1
),
CategoryShare AS (
    SELECT ci.db_year, c.pcf_violation_category, CAST(COUNT(*) AS REAL) AS category_count, 
           (SELECT CAST(COUNT(*) AS REAL) FROM collisions c2 JOIN case_ids ci2 ON c2.case_id = ci2.case_id WHERE ci2.db_year = ci.db_year) AS total_count
    FROM collisions c
    JOIN case_ids ci ON c.case_id = ci.case_id
    WHERE c.pcf_violation_category = (SELECT pcf_violation_category FROM MostCommonCategory2021)
    GROUP BY ci.db_year, c.pcf_violation_category
)
SELECT 
    (SELECT (category_count / total_count) * 100.0 FROM CategoryShare WHERE db_year = 2021) -
    (SELECT (category_count / total_count) * 100.0 FROM CategoryShare WHERE db_year = 2011) AS percentage_point_decrease
FROM CategoryShare
LIMIT 1;