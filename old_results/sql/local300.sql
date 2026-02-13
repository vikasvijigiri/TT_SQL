WITH RECURSIVE date_series AS (
  SELECT customer_id, MIN(txn_date) AS txn_date, MAX(txn_date) AS max_date
  FROM customer_transactions
  GROUP BY customer_id
  UNION ALL
  SELECT ds.customer_id, date(ds.txn_date, '+1 day'), ds.max_date
  FROM date_series ds
  WHERE date(ds.txn_date, '+1 day') <= ds.max_date
),
customer_daily_balances AS (
  SELECT ds.customer_id, ds.txn_date,
         COALESCE(SUM(ct.txn_amount), 0) AS daily_balance
  FROM date_series ds
  LEFT JOIN customer_transactions ct
  ON ds.customer_id = ct.customer_id AND ds.txn_date = ct.txn_date
  GROUP BY ds.customer_id, ds.txn_date
),
customer_balances_carried_forward AS (
  SELECT customer_id, txn_date,
         CASE WHEN daily_balance < 0 THEN 0 ELSE daily_balance END AS non_negative_balance
  FROM customer_daily_balances
),
customer_balances_final AS (
  SELECT customer_id, txn_date, non_negative_balance AS final_balance
  FROM customer_balances_carried_forward
  WHERE txn_date = (SELECT MIN(txn_date) FROM customer_balances_carried_forward WHERE customer_id = cbcf.customer_id)
  UNION ALL
  SELECT cbcf.customer_id, cbcf.txn_date,
         CASE WHEN cbcf.non_negative_balance IS NULL THEN cbf.final_balance ELSE cbcf.non_negative_balance END AS final_balance
  FROM customer_balances_carried_forward cbcf
  JOIN customer_balances_final cbf ON cbcf.customer_id = cbf.customer_id AND date(cbf.txn_date, '+1 day') = cbcf.txn_date
),
monthly_max_balances AS (
  SELECT customer_id, strftime('%Y-%m', txn_date) AS month,
         MAX(final_balance) AS max_daily_balance
  FROM customer_balances_final
  GROUP BY customer_id, month
)
SELECT month, SUM(max_daily_balance) AS total_max_balance
FROM monthly_max_balances
GROUP BY month
ORDER BY month;