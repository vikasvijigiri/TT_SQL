SELECT employeeid, late_orders, (CAST(late_orders AS REAL) / CAST(total_orders AS REAL)) * 100 AS late_order_percentage
FROM (
  SELECT o.employeeid,
         COUNT(*) AS total_orders,
         SUM(CASE WHEN o.shippeddate > o.requireddate THEN 1 ELSE 0 END) AS late_orders
  FROM orders o
  GROUP BY o.employeeid
  HAVING COUNT(*) > 50
) AS employee_orders
ORDER BY late_order_percentage DESC
LIMIT 3;