WITH monthly_balances AS (
    SELECT 
        strftime('%Y-%m', txn_date) AS month_year,
        customer_id,
        SUM(txn_amount) AS total_balance
    FROM customer_transactions
    WHERE txn_date <= date(strftime('%Y-%m', txn_date) || '-01')
    GROUP BY month_year, customer_id
),
monthly_totals AS (
    SELECT 
        month_year,
        SUM(CASE WHEN total_balance < 0 THEN 0 ELSE total_balance END) AS total_balance
    FROM monthly_balances
    GROUP BY month_year
),
previous_month_totals AS (
    SELECT 
        month_year,
        LAG(total_balance, 1) OVER (ORDER BY month_year) AS previous_month_balance
    FROM monthly_totals
)
SELECT 
    month_year,
    previous_month_balance
FROM previous_month_totals
WHERE previous_month_balance IS NOT NULL
AND month_year > (SELECT MIN(month_year) FROM monthly_totals)
ORDER BY month_year;