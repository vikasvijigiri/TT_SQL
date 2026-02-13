WITH MonthlyBalances AS (
  SELECT 
    customer_id,
    strftime('%Y-%m', txn_date) AS month_year,
    SUM(CASE WHEN txn_type = 'deposit' THEN txn_amount ELSE 0 END) -
    SUM(CASE WHEN txn_type = 'withdrawal' THEN txn_amount ELSE 0 END) AS month_end_balance
  FROM customer_transactions
  WHERE strftime('%Y', txn_date) = '2020'
  GROUP BY customer_id, month_year
),
PositiveBalanceCounts AS (
  SELECT 
    month_year,
    COUNT(DISTINCT customer_id) AS positive_balance_count
  FROM MonthlyBalances
  WHERE month_end_balance > 0
  GROUP BY month_year
),
MaxMinMonths AS (
  SELECT 
    MAX(positive_balance_count) AS max_count,
    MIN(positive_balance_count) AS min_count
  FROM PositiveBalanceCounts
),
MaxMonth AS (
  SELECT 
    month_year
  FROM PositiveBalanceCounts, MaxMinMonths
  WHERE positive_balance_count = max_count
  LIMIT 1
),
MinMonth AS (
  SELECT 
    month_year
  FROM PositiveBalanceCounts, MaxMinMonths
  WHERE positive_balance_count = min_count
  LIMIT 1
),
AverageBalances AS (
  SELECT 
    'max' AS type,
    AVG(CAST(month_end_balance AS REAL)) AS average_balance
  FROM MonthlyBalances
  WHERE month_year = (SELECT month_year FROM MaxMonth)
  UNION ALL
  SELECT 
    'min' AS type,
    AVG(CAST(month_end_balance AS REAL)) AS average_balance
  FROM MonthlyBalances
  WHERE month_year = (SELECT month_year FROM MinMonth)
)
SELECT 
  (SELECT average_balance FROM AverageBalances WHERE type = 'max') -
  (SELECT average_balance FROM AverageBalances WHERE type = 'min') AS balance_difference
FROM AverageBalances
LIMIT 1;