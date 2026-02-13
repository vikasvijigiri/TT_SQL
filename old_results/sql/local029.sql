WITH DeliveredOrders AS (
    SELECT o.customer_id, o.order_id
    FROM olist_orders o
    WHERE o.order_status = 'delivered'
),
CustomerOrderCounts AS (
    SELECT c.customer_unique_id, c.customer_city, c.customer_state, COUNT(do.order_id) AS delivered_order_count
    FROM DeliveredOrders do
    JOIN olist_customers c ON do.customer_id = c.customer_id
    GROUP BY c.customer_unique_id, c.customer_city, c.customer_state
),
CustomerPayments AS (
    SELECT do.order_id, c.customer_unique_id, op.payment_value
    FROM DeliveredOrders do
    JOIN olist_order_payments op ON do.order_id = op.order_id
    JOIN olist_customers c ON do.customer_id = c.customer_id
),
TopCustomers AS (
    SELECT coc.customer_unique_id, coc.customer_city, coc.customer_state, coc.delivered_order_count
    FROM CustomerOrderCounts coc
    ORDER BY coc.delivered_order_count DESC
    LIMIT 3
)
SELECT tc.customer_unique_id, AVG(cp.payment_value) AS avg_payment_value, tc.customer_city, tc.customer_state
FROM TopCustomers tc
JOIN CustomerPayments cp ON tc.customer_unique_id = cp.customer_unique_id
GROUP BY tc.customer_unique_id, tc.customer_city, tc.customer_state;