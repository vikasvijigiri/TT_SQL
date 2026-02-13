WITH YearlyCauses AS (
    SELECT 
        ci.db_year AS year,
        c.primary_collision_factor AS cause,
        COUNT(*) AS cause_count
    FROM 
        collisions c
    JOIN 
        case_ids ci ON c.case_id = ci.case_id
    GROUP BY 
        ci.db_year, c.primary_collision_factor
),
TopCausesPerYear AS (
    SELECT 
        year, 
        cause,
        cause_count,
        ROW_NUMBER() OVER (PARTITION BY year ORDER BY cause_count DESC) AS rank
    FROM 
        YearlyCauses
),
TopTwoCauses AS (
    SELECT 
        year, 
        cause
    FROM 
        TopCausesPerYear
    WHERE 
        rank <= 2
),
DistinctTopTwoCauses AS (
    SELECT 
        year,
        GROUP_CONCAT(cause, '|') AS top_causes
    FROM 
        TopTwoCauses
    GROUP BY 
        year
),
UniqueTopCauses AS (
    SELECT 
        dtc1.year
    FROM 
        DistinctTopTwoCauses dtc1
    LEFT JOIN 
        DistinctTopTwoCauses dtc2 ON dtc1.top_causes = dtc2.top_causes AND dtc1.year != dtc2.year
    WHERE 
        dtc2.year IS NULL
)
SELECT 
    year
FROM 
    UniqueTopCauses
ORDER BY 
    year;