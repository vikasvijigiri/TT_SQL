WITH order_lines AS (
    SELECT ol.id AS line_id,
           ol.product_id,
           ol.qty AS line_qty,
           SUM(ol.qty) OVER (PARTITION BY ol.product_id ORDER BY ol.id) AS cum_req,
           SUM(ol.qty) OVER (PARTITION BY ol.product_id ORDER BY ol.id) - ol.qty AS prev_cum_req
    FROM orderlines ol
    WHERE ol.order_id = 423
),
inv_sorted AS (
    SELECT inv.id AS inv_id,
           inv.product_id,
           inv.qty AS inv_qty,
           loc.aisle,
           loc.position,
           p.purchased,
           SUM(inv.qty) OVER (PARTITION BY inv.product_id ORDER BY p.purchased ASC, inv.qty ASC) AS cum_inv,
           SUM(inv.qty) OVER (PARTITION BY inv.product_id ORDER BY p.purchased ASC, inv.qty ASC) - inv.qty AS prev_cum_inv
    FROM inventory inv
    JOIN locations loc ON inv.location_id = loc.id
    JOIN purchases p ON inv.purchase_id = p.id
    WHERE loc.warehouse = 1
)
SELECT l.line_id,
       i.product_id,
       i.aisle,
       i.position,
       CASE
           WHEN min(i.cum_inv, l.cum_req) > max(i.prev_cum_inv, l.prev_cum_req)
           THEN min(i.cum_inv, l.cum_req) - max(i.prev_cum_inv, l.prev_cum_req)
           ELSE 0
       END AS pick_qty
FROM order_lines l
JOIN inv_sorted i ON i.product_id = l.product_id
WHERE min(i.cum_inv, l.cum_req) > max(i.prev_cum_inv, l.prev_cum_req)
ORDER BY i.product_id, l.line_id, i.purchased, i.inv_qty;