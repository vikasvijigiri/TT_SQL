WITH top_containers AS (
    SELECT p.id, p.name
    FROM packaging p
    LEFT JOIN packaging_relations pr ON p.id = pr.contains_id
    WHERE pr.packaging_id IS NULL
), recursive_desc AS (
    SELECT tc.id AS top_id, pr.contains_id AS item_id, pr.qty AS cum_qty
    FROM top_containers tc
    JOIN packaging_relations pr ON pr.packaging_id = tc.id
    UNION ALL
    SELECT rd.top_id, pr.contains_id, rd.cum_qty * pr.qty
    FROM recursive_desc rd
    JOIN packaging_relations pr ON pr.packaging_id = rd.item_id
)
SELECT tc.name AS container_name,
       i.name AS item_name,
       SUM(rd.cum_qty) AS total_quantity
FROM recursive_desc rd
JOIN top_containers tc ON rd.top_id = tc.id
JOIN packaging i ON i.id = rd.item_id
WHERE NOT EXISTS (
    SELECT 1 FROM packaging_relations pr2 WHERE pr2.packaging_id = rd.item_id
)
GROUP BY tc.id, tc.name, i.id, i.name
HAVING SUM(rd.cum_qty) > 500;