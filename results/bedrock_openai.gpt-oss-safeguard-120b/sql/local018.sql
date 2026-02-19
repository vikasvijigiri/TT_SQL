WITH filtered AS (
    SELECT pcf_violation_category,
           substr(collision_date, 1, 4) AS year
    FROM collisions
    WHERE substr(collision_date, 1, 4) IN ('2011', '2021')
      AND pcf_violation_category IS NOT NULL
),
total_counts AS (
    SELECT year,
           COUNT(*) AS total_count
    FROM filtered
    GROUP BY year
),
category_counts AS (
    SELECT year,
           pcf_violation_category,
           COUNT(*) AS category_count
    FROM filtered
    GROUP BY year, pcf_violation_category
),
shares AS (
    SELECT c.year,
           c.pcf_violation_category,
           c.category_count * 100.0 / t.total_count AS share_percent
    FROM category_counts c
    JOIN total_counts t ON c.year = t.year
),
top_2021 AS (
    SELECT pcf_violation_category
    FROM category_counts
    WHERE year = '2021'
    ORDER BY category_count DESC
    LIMIT 1
),
selected_shares AS (
    SELECT s.year,
           s.share_percent
    FROM shares s
    JOIN top_2021 t ON s.pcf_violation_category = t.pcf_violation_category
    WHERE s.year IN ('2011', '2021')
)
SELECT
    MAX(CASE WHEN year = '2011' THEN share_percent END) -
    MAX(CASE WHEN year = '2021' THEN share_percent END) AS percentage_point_decrease
FROM selected_shares;