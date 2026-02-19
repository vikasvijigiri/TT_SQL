WITH cause_counts AS (
    SELECT CAST(strftime('%Y', c.collision_date) AS INTEGER) AS year,
           LOWER(c.primary_collision_factor) AS cause,
           COUNT(*) AS cnt
    FROM collisions c
    JOIN case_ids ci ON c.case_id = ci.case_id
    WHERE c.primary_collision_factor IS NOT NULL
    GROUP BY year, cause
),
ranked_causes AS (
    SELECT year,
           cause,
           cnt,
           ROW_NUMBER() OVER (PARTITION BY year ORDER BY cnt DESC, cause) AS rn
    FROM cause_counts
),
top_two AS (
    SELECT year,
           GROUP_CONCAT(cause, '|') AS top_two_set
    FROM (
        SELECT year, cause
        FROM ranked_causes
        WHERE rn <= 2
        ORDER BY year, cause
    )
    GROUP BY year
),
set_counts AS (
    SELECT top_two_set,
           COUNT(*) AS set_cnt
    FROM top_two
    GROUP BY top_two_set
)
SELECT t.year
FROM top_two t
JOIN set_counts s ON t.top_two_set = s.top_two_set
WHERE s.set_cnt = 1;