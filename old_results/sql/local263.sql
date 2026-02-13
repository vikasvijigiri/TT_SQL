WITH step_scores AS (
  SELECT
    name,
    version,
    step,
    MAX(CASE WHEN model = 'Stack' THEN test_score END) AS stack_score,
    MAX(CASE WHEN model != 'Stack' THEN test_score END) AS max_non_stack_score
  FROM model_score
  GROUP BY name, version, step
),
model_status AS (
  SELECT
    name,
    version,
    CASE
      WHEN MAX(CASE WHEN stack_score > max_non_stack_score THEN 1 ELSE 0 END) = 1 THEN 'strong'
      WHEN MAX(CASE WHEN stack_score = max_non_stack_score THEN 1 ELSE 0 END) = 1 THEN 'soft'
      ELSE NULL
    END AS status
  FROM step_scores
  GROUP BY name, version
),
model_l1 AS (
  SELECT DISTINCT name, version, L1_model
  FROM model
),
status_counts AS (
  SELECT
    ml.L1_model,
    ms.status,
    COUNT(*) AS cnt
  FROM model_status ms
  JOIN model_l1 ml ON ms.name = ml.name AND ms.version = ml.version
  WHERE ms.status IS NOT NULL
  GROUP BY ml.L1_model, ms.status
),
ranked AS (
  SELECT
    L1_model,
    status,
    cnt,
    ROW_NUMBER() OVER (PARTITION BY status ORDER BY cnt DESC) AS rn
  FROM status_counts
)
SELECT L1_model, status, cnt
FROM ranked
WHERE rn = 1;