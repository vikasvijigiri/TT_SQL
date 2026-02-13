WITH RECURSIVE
product_start AS (
    SELECT p.id AS product_id,
           COALESCE(pur.pur_qty, 0) - COALESCE(sal.sales_qty, 0) AS start_qty,
           COALESCE(pm.qty_minimum, 0) AS min_qty
    FROM products p
    LEFT JOIN (
        SELECT product_id, SUM(qty) AS pur_qty
        FROM purchases
        WHERE purchased <= '2018-12-31'
        GROUP BY product_id
    ) pur ON pur.product_id = p.id
    LEFT JOIN (
        SELECT product_id, SUM(qty) AS sales_qty
        FROM monthly_sales
        WHERE mth <= '2018-12'
        GROUP BY product_id
    ) sal ON sal.product_id = p.id
    LEFT JOIN product_minimums pm ON pm.product_id = p.id
),
months AS (
    SELECT 1 AS month_num, '2019-01' AS mth
    UNION ALL
    SELECT month_num + 1, printf('2019-%02d', month_num + 1)
    FROM months
    WHERE month_num < 12
),
rec AS (
    -- January
    SELECT ps.product_id,
           m.month_num,
           m.mth,
           CASE WHEN ps.start_qty - COALESCE(s.qty, 0) < ps.min_qty THEN ps.min_qty
                ELSE ps.start_qty - COALESCE(s.qty, 0)
           END AS ending_qty,
           ps.min_qty,
           ABS(CASE WHEN ps.start_qty - COALESCE(s.qty, 0) < ps.min_qty THEN ps.min_qty
                    ELSE ps.start_qty - COALESCE(s.qty, 0)
               END - ps.min_qty) AS diff
    FROM product_start ps
    JOIN months m ON m.month_num = 1
    LEFT JOIN monthly_sales s ON s.product_id = ps.product_id AND s.mth = m.mth
    UNION ALL
    -- Subsequent months
    SELECT r.product_id,
           m.month_num,
           m.mth,
           CASE WHEN r.ending_qty - COALESCE(s.qty, 0) < r.min_qty THEN r.min_qty
                ELSE r.ending_qty - COALESCE(s.qty, 0)
           END AS ending_qty,
           r.min_qty,
           ABS(CASE WHEN r.ending_qty - COALESCE(s.qty, 0) < r.min_qty THEN r.min_qty
                    ELSE r.ending_qty - COALESCE(s.qty, 0)
               END - r.min_qty) AS diff
    FROM rec r
    JOIN months m ON m.month_num = r.month_num + 1
    LEFT JOIN monthly_sales s ON s.product_id = r.product_id AND s.mth = m.mth
)
SELECT product_id,
       mth AS month,
       diff AS absolute_difference
FROM (
    SELECT product_id,
           mth,
           diff,
           ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY diff ASC, month_num) AS rn
    FROM rec
) t
WHERE rn = 1;