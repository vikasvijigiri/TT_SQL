WITH RECURSIVE rec(root_id, item_id, total_qty) AS (
    SELECT pr.packaging_id, pr.contains_id, pr.qty
    FROM packaging_relations pr
    UNION ALL
    SELECT rec.root_id, pr.contains_id, rec.total_qty * pr.qty
    FROM rec
    JOIN packaging_relations pr ON rec.item_id = pr.packaging_id
),
roots AS (
    SELECT packaging_id AS root_id
    FROM packaging_relations
    EXCEPT
    SELECT contains_id FROM packaging_relations
)
SELECT AVG(total_leaf_qty) AS avg_total_quantity
FROM (
    SELECT r.root_id, SUM(rec.total_qty) AS total_leaf_qty
    FROM roots r
    JOIN rec ON rec.root_id = r.root_id
    WHERE rec.item_id NOT IN (SELECT packaging_id FROM packaging_relations)
    GROUP BY r.root_id
) sub;