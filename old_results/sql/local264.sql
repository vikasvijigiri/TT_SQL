WITH stack AS (
    SELECT L1_model
    FROM model
    WHERE name = 'Stack'
),
traditional AS (
    SELECT L1_model
    FROM model
    WHERE name <> 'Stack'
),
combined AS (
    SELECT L1_model FROM stack
    UNION ALL
    SELECT L1_model FROM traditional
)
SELECT L1_model, COUNT(*) AS total_count
FROM combined
GROUP BY L1_model
ORDER BY total_count DESC
LIMIT 1