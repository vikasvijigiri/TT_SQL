WITH inv_range AS (
    SELECT i.id AS inv_id,
           i.product_id,
           i.qty AS inv_qty,
           p.purchased,
           SUM(i.qty) OVER (PARTITION BY i.product_id ORDER BY p.purchased ASC, i.qty ASC) AS cum_inv_qty,
           (SUM(i.qty) OVER (PARTITION BY i.product_id ORDER BY p.purchased ASC, i.qty ASC) - i.qty + 1) AS inv_start,
           SUM(i.qty) OVER (PARTITION BY i.product_id ORDER BY p.purchased ASC, i.qty ASC) AS inv_end
    FROM inventory i
    JOIN purchases p ON i.purchase_id = p.id
),
order_range AS (
    SELECT ol.id AS orderline_id,
           ol.product_id,
           ol.qty AS order_qty,
           o.ordered,
           SUM(ol.qty) OVER (PARTITION BY ol.product_id ORDER BY o.ordered ASC, ol.id ASC) AS cum_order_qty,
           (SUM(ol.qty) OVER (PARTITION BY ol.product_id ORDER BY o.ordered ASC, ol.id ASC) - ol.qty + 1) AS order_start,
           SUM(ol.qty) OVER (PARTITION BY ol.product_id ORDER BY o.ordered ASC, ol.id ASC) AS order_end
    FROM orderlines ol
    JOIN orders o ON ol.order_id = o.id
),
alloc AS (
    SELECT orl.orderline_id,
           orl.product_id,
           orl.order_qty,
           COALESCE(SUM(
               CASE 
                   WHEN inv.inv_end < orl.order_start OR inv.inv_start > orl.order_end THEN 0
                   ELSE MIN(inv.inv_end, orl.order_end) - MAX(inv.inv_start, orl.order_start) + 1
               END
           ), 0) AS allocated_qty
    FROM order_range orl
    JOIN inv_range inv ON inv.product_id = orl.product_id
    GROUP BY orl.orderline_id, orl.product_id, orl.order_qty
),
pick AS (
    SELECT a.product_id,
           CASE WHEN a.order_qty = 0 THEN 0.0
                ELSE CAST(a.allocated_qty AS REAL) / a.order_qty END AS pick_pct
    FROM alloc a
)
SELECT p.name AS product_name,
       AVG(pick_pct) AS avg_pick_percentage
FROM pick
JOIN products p ON p.id = pick.product_id
GROUP BY p.name
ORDER BY p.name;