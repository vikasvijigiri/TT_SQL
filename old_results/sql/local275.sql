WITH ma AS (
  SELECT
    product_id,
    mth,
    qty,
    AVG(qty) OVER (PARTITION BY product_id ORDER BY mth ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) AS mov_avg
  FROM monthly_sales
  WHERE mth >= '2016-01'
), ratios AS (
  SELECT
    product_id,
    mth,
    CAST(qty AS REAL) / mov_avg AS ratio
  FROM ma
  WHERE substr(mth, 1, 4) = '2017' AND mov_avg IS NOT NULL
)
SELECT p.id, p.name
FROM ratios r
JOIN products p ON p.id = r.product_id
GROUP BY p.id, p.name
HAVING MIN(ratio) > 2 AND COUNT(DISTINCT r.mth) = 12;