WITH CustomerSpending AS (
    SELECT o.customerid, SUM(od.unitprice * od.quantity) AS total_spent
    FROM orders o
    JOIN order_details od ON o.orderid = od.orderid
    WHERE o.orderdate BETWEEN '1998-01-01' AND '1998-12-31'
    GROUP BY o.customerid
),
SpendingGroups AS (
    SELECT cs.customerid, cs.total_spent, cgt.groupname
    FROM CustomerSpending cs
    JOIN customergroupthreshold cgt ON cs.total_spent >= cgt.rangebottom AND cs.total_spent < cgt.rangetop
),
CustomerCounts AS (
    SELECT groupname, COUNT(DISTINCT customerid) AS customer_count
    FROM SpendingGroups
    GROUP BY groupname
),
TotalCustomers AS (
    SELECT COUNT(DISTINCT o.customerid) AS total_customers
    FROM orders o
    WHERE o.orderdate BETWEEN '1998-01-01' AND '1998-12-31'
)
SELECT cc.groupname, cc.customer_count, 
       CASE WHEN tc.total_customers > 0 THEN (CAST(cc.customer_count AS REAL) / tc.total_customers) * 100 ELSE 0 END AS percentage_of_total
FROM CustomerCounts cc, TotalCustomers tc;