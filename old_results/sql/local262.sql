WITH stack_scores AS (
    SELECT name, version, step, test_score AS stack_test
    FROM model_score
    WHERE model = 'Stack' AND step IN (1, 2, 3)
),
nonstack_max AS (
    SELECT name, version, step, MAX(test_score) AS max_nonstack_test
    FROM model_score
    WHERE model != 'Stack' AND step IN (1, 2, 3)
    GROUP BY name, version, step
),
cond AS (
    SELECT s.name
    FROM stack_scores s
    JOIN nonstack_max n ON s.name = n.name AND s.version = n.version AND s.step = n.step
    WHERE s.stack_test > n.max_nonstack_test
),
cond_counts AS (
    SELECT name, COUNT(*) AS cnt_cond
    FROM cond
    GROUP BY name
),
solution_counts AS (
    SELECT name, COUNT(*) AS cnt_sol
    FROM solution
    GROUP BY name
)
SELECT c.name
FROM cond_counts c
JOIN solution_counts s ON c.name = s.name
WHERE c.cnt_cond > s.cnt_sol;