WITH periods AS (
  SELECT week_date,
         CASE 
           WHEN week_date >= date('2020-06-15', '-84 days') AND week_date < date('2020-06-15') THEN 'before'
           WHEN week_date > date('2020-06-15') AND week_date <= date('2020-06-15', '+84 days') THEN 'after'
         END AS period
  FROM cleaned_weekly_sales
  WHERE week_date >= date('2020-06-15', '-84 days')
    AND week_date <= date('2020-06-15', '+84 days')
    AND week_date <> date('2020-06-15')
), sales_by_attr AS (
  SELECT region AS attr_value,
         'region' AS attr_type,
         period,
         SUM(sales) AS total_sales
  FROM cleaned_weekly_sales
  JOIN periods USING (week_date)
  GROUP BY region, period
  UNION ALL
  SELECT platform AS attr_value,
         'platform' AS attr_type,
         period,
         SUM(sales) AS total_sales
  FROM cleaned_weekly_sales
  JOIN periods USING (week_date)
  GROUP BY platform, period
  UNION ALL
  SELECT age_band AS attr_value,
         'age_band' AS attr_type,
         period,
         SUM(sales) AS total_sales
  FROM cleaned_weekly_sales
  JOIN periods USING (week_date)
  GROUP BY age_band, period
  UNION ALL
  SELECT demographic AS attr_value,
         'demographic' AS attr_type,
         period,
         SUM(sales) AS total_sales
  FROM cleaned_weekly_sales
  JOIN periods USING (week_date)
  GROUP BY demographic, period
  UNION ALL
  SELECT customer_type AS attr_value,
         'customer_type' AS attr_type,
         period,
         SUM(sales) AS total_sales
  FROM cleaned_weekly_sales
  JOIN periods USING (week_date)
  GROUP BY customer_type, period
), pivot AS (
  SELECT attr_type,
         attr_value,
         MAX(CASE WHEN period = 'before' THEN total_sales END) AS before_sales,
         MAX(CASE WHEN period = 'after' THEN total_sales END) AS after_sales
  FROM sales_by_attr
  GROUP BY attr_type, attr_value
), pct_change AS (
  SELECT attr_type,
         attr_value,
         CASE WHEN before_sales IS NULL OR before_sales = 0 THEN NULL
              ELSE ((after_sales - before_sales) * 100.0) / before_sales
         END AS pct_change
  FROM pivot
  WHERE before_sales IS NOT NULL AND after_sales IS NOT NULL
), avg_change AS (
  SELECT attr_type,
         AVG(pct_change) AS avg_pct_change
  FROM pct_change
  GROUP BY attr_type
)
SELECT attr_type,
       avg_pct_change
FROM avg_change
ORDER BY avg_pct_change ASC
LIMIT 1;