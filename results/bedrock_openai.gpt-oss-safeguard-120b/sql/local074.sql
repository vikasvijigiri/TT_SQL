WITH date_bounds AS (
    SELECT DATE(MIN(txn_date), 'start of month') AS min_month,
           DATE(MAX(txn_date), 'start of month') AS max_month
    FROM customer_transactions
),
months AS (
    SELECT min_month AS month_start
    FROM date_bounds
    UNION ALL
    SELECT DATE(month_start, '+1 month')
    FROM months, date_bounds
    WHERE month_start < date_bounds.max_month
),
customers AS (
    SELECT DISTINCT customer_id
    FROM customer_transactions
),
monthly_txn AS (
    SELECT customer_id,
           DATE(txn_date, 'start of month') AS month_start,
           SUM(txn_amount) AS monthly_txn_sum
    FROM customer_transactions
    GROUP BY customer_id, DATE(txn_date, 'start of month')
),
customer_months AS (
    SELECT c.customer_id, m.month_start
    FROM customers c CROSS JOIN months m
),
joined AS (
    SELECT cm.customer_id,
           cm.month_start,
           COALESCE(mt.monthly_txn_sum, 0) AS monthly_txn_sum
    FROM customer_months cm
    LEFT JOIN monthly_txn mt
        ON cm.customer_id = mt.customer_id
       AND cm.month_start = mt.month_start
),
balance_calc AS (
    SELECT customer_id,
           month_start AS month,
           SUM(monthly_txn_sum) OVER (PARTITION BY customer_id ORDER BY month_start ROWS UNBOUNDED PRECEDING) AS closing_balance
    FROM joined
),
final AS (
    SELECT customer_id,
           month,
           closing_balance,
           closing_balance - COALESCE(LAG(closing_balance) OVER (PARTITION BY customer_id ORDER BY month), 0) AS monthly_change
    FROM balance_calc
)
SELECT customer_id,
       month,
       closing_balance,
       monthly_change,
       closing_balance AS cumulative_balance
FROM final
ORDER BY customer_id, month;