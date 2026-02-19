WITH daily_sales AS (
    SELECT DATE(o.order_purchase_timestamp) AS sale_date,
           SUM(oi.price) AS daily_sales
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE LOWER(p.product_category_name) = 'toys'
      AND DATE(o.order_purchase_timestamp) BETWEEN '2017-01-01' AND '2018-08-29'
    GROUP BY sale_date
),
regression_stats AS (
    SELECT COUNT(*) AS n,
           SUM(julianday(sale_date)) AS sum_x,
           SUM(daily_sales) AS sum_y,
           SUM(julianday(sale_date) * daily_sales) AS sum_xy,
           SUM(julianday(sale_date) * julianday(sale_date)) AS sum_x2
    FROM daily_sales
),
regression_params AS (
    SELECT 
        (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) AS beta1,
        (sum_y - ((n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)) * sum_x) / n AS beta0
    FROM regression_stats
),
prediction_dates AS (
    SELECT '2018-12-03' AS pred_date UNION ALL
    SELECT '2018-12-04' UNION ALL
    SELECT '2018-12-05' UNION ALL
    SELECT '2018-12-06' UNION ALL
    SELECT '2018-12-07' UNION ALL
    SELECT '2018-12-08' UNION ALL
    SELECT '2018-12-09'
),
predictions AS (
    SELECT pd.pred_date,
           rp.beta0 + rp.beta1 * julianday(pd.pred_date) AS predicted_sales
    FROM prediction_dates pd
    CROSS JOIN regression_params rp
),
target_dates AS (
    SELECT '2018-12-05' AS target_date UNION ALL
    SELECT '2018-12-06' UNION ALL
    SELECT '2018-12-07' UNION ALL
    SELECT '2018-12-08'
),
moving_averages AS (
    SELECT td.target_date,
           AVG(p.predicted_sales) AS moving_average
    FROM target_dates td
    JOIN predictions p
      ON p.pred_date BETWEEN DATE(td.target_date, '-2 day') AND DATE(td.target_date, '+2 day')
    GROUP BY td.target_date
)
SELECT 
    MAX(CASE WHEN target_date = '2018-12-05' THEN moving_average END) AS ma_2018_12_05,
    MAX(CASE WHEN target_date = '2018-12-06' THEN moving_average END) AS ma_2018_12_06,
    MAX(CASE WHEN target_date = '2018-12-07' THEN moving_average END) AS ma_2018_12_07,
    MAX(CASE WHEN target_date = '2018-12-08' THEN moving_average END) AS ma_2018_12_08,
    (MAX(CASE WHEN target_date = '2018-12-05' THEN moving_average END) +
     MAX(CASE WHEN target_date = '2018-12-06' THEN moving_average END) +
     MAX(CASE WHEN target_date = '2018-12-07' THEN moving_average END) +
     MAX(CASE WHEN target_date = '2018-12-08' THEN moving_average END)) AS total_sum
FROM moving_averages;