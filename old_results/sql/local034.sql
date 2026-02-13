WITH PaymentCounts AS (
    SELECT 
        p.product_category_name,
        op.payment_type,
        COUNT(*) AS payment_count
    FROM olist_order_payments op
    JOIN olist_order_items oi ON op.order_id = oi.order_id
    JOIN olist_products p ON oi.product_id = p.product_id
    GROUP BY p.product_category_name, op.payment_type
),
RankedPayments AS (
    SELECT 
        pc.product_category_name,
        pc.payment_type,
        pc.payment_count,
        ROW_NUMBER() OVER (PARTITION BY pc.product_category_name ORDER BY pc.payment_count DESC, pc.payment_type ASC) AS rank
    FROM PaymentCounts pc
),
MostPreferredPayments AS (
    SELECT 
        rp.product_category_name,
        rp.payment_type,
        rp.payment_count
    FROM RankedPayments rp
    WHERE rp.rank = 1
),
TotalPayments AS (
    SELECT 
        SUM(payment_count) AS total_payment_count
    FROM MostPreferredPayments
)
SELECT 
    AVG(CAST(total_payment_count AS REAL)) AS average_payments
FROM TotalPayments;