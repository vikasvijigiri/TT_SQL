SELECT p.name AS product_name,
       AVG(f.qty) AS avg_qty
FROM (
    SELECT pl.product_id, pl.qty, plog.log_time
    FROM picking_line pl
    JOIN picking_log plog
      ON pl.picklist_id = plog.picklist_id
     AND pl.line_no = plog.pickline_no
    WHERE pl.order_id = 421
    ORDER BY plog.log_time
) AS f
JOIN products p ON f.product_id = p.id
GROUP BY p.id, p.name