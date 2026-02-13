WITH DailyRunningBalance AS (
    SELECT 
        customer_id,
        txn_date,
        SUM(CASE WHEN txn_type = 'deposit' THEN txn_amount ELSE -txn_amount END) OVER (PARTITION BY customer_id ORDER BY DATE(txn_date) ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance
    FROM customer_transactions
),
RollingAverageBalance AS (
    SELECT 
        customer_id,
        txn_date,
        CASE WHEN COUNT(*) OVER (PARTITION BY customer_id ORDER BY DATE(txn_date) ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) < 30 THEN 0
             ELSE CASE WHEN AVG(running_balance) OVER (PARTITION BY customer_id ORDER BY DATE(txn_date) ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) < 0 THEN 0
                       ELSE AVG(running_balance) OVER (PARTITION BY customer_id ORDER BY DATE(txn_date) ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
                  END
        END AS rolling_avg_balance
    FROM DailyRunningBalance
),
FilteredTransactions AS (
    SELECT 
        rab.customer_id,
        rab.txn_date,
        rab.rolling_avg_balance,
        strftime('%Y-%m', DATE(rab.txn_date)) AS month_year,
        strftime('%Y-%m', MIN(DATE(rab.txn_date)) OVER (PARTITION BY rab.customer_id)) AS first_month
    FROM RollingAverageBalance rab
),
MonthlyMaxBalance AS (
    SELECT 
        customer_id,
        month_year,
        MAX(rolling_avg_balance) AS max_rolling_avg_balance
    FROM FilteredTransactions
    WHERE month_year > first_month
    GROUP BY customer_id, month_year
),
MonthlyTotalMaxBalance AS (
    SELECT 
        month_year,
        SUM(max_rolling_avg_balance) AS total_max_balance
    FROM MonthlyMaxBalance
    GROUP BY month_year
)
SELECT *
FROM MonthlyTotalMaxBalance;