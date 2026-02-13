WITH base AS (
  SELECT
    product_id,
    mth,
    qty,
    ((CAST(substr(mth,1,4) AS INTEGER) - 2016) * 12 + (CAST(substr(mth,6,2) AS INTEGER) - 1) + 1) AS x,
    CASE
      WHEN ((CAST(substr(mth,1,4) AS INTEGER) - 2016) * 12 + (CAST(substr(mth,6,2) AS INTEGER) - 1) + 1) BETWEEN 7 AND 30
      THEN qty * 1.1
      ELSE qty
    END AS adj_qty,
    CASE
      WHEN ((CAST(substr(mth,1,4) AS INTEGER) - 2016) * 12 + (CAST(substr(mth,6,2) AS INTEGER) - 1) + 1) BETWEEN 7 AND 30
      THEN 2.0
      ELSE 1.0
    END AS weight
  FROM monthly_sales
  WHERE product_id IN (4160, 7790)
    AND mth >= '2016-01' AND mth <= '2018-12'
),
training AS (
  SELECT * FROM base WHERE x <= 24
),
reg AS (
  SELECT
    product_id,
    SUM(weight) AS sum_w,
    SUM(weight * x) AS sum_wx,
    SUM(weight * adj_qty) AS sum_wy,
    SUM(weight * x * adj_qty) AS sum_wxy,
    SUM(weight * x * x) AS sum_wxx
  FROM training
  GROUP BY product_id
),
coeff AS (
  SELECT
    product_id,
    (CAST(sum_w AS REAL) * sum_wxy - sum_wx * sum_wy) / (CAST(sum_w AS REAL) * sum_wxx - sum_wx * sum_wx) AS slope,
    (sum_wy - ((CAST(sum_w AS REAL) * sum_wxy - sum_wx * sum_wy) / (CAST(sum_w AS REAL) * sum_wxx - sum_wx * sum_wx)) * sum_wx) / CAST(sum_w AS REAL) AS intercept
  FROM reg
),
forecast AS (
  SELECT
    b.product_id,
    b.x,
    c.intercept + c.slope * b.x AS forecast_qty
  FROM base b
  JOIN coeff c ON b.product_id = c.product_id
  WHERE b.x BETWEEN 25 AND 36
)
SELECT AVG(annual_forecast) AS avg_forecasted_annual_sales
FROM (
  SELECT product_id, SUM(forecast_qty) AS annual_forecast
  FROM forecast
  GROUP BY product_id
) sub;