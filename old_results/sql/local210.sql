WITH feb AS (
    SELECT s.hub_id, COUNT(o.order_id) AS feb_cnt
    FROM orders o
    JOIN stores s ON o.store_id = s.store_id
    WHERE o.order_status = 'finished' AND o.order_created_month = 2
    GROUP BY s.hub_id
), mar AS (
    SELECT s.hub_id, COUNT(o.order_id) AS mar_cnt
    FROM orders o
    JOIN stores s ON o.store_id = s.store_id
    WHERE o.order_status = 'finished' AND o.order_created_month = 3
    GROUP BY s.hub_id
), combined AS (
    SELECT h.hub_id, h.hub_name,
           COALESCE(feb.feb_cnt, 0) AS feb_cnt,
           COALESCE(mar.mar_cnt, 0) AS mar_cnt,
           CASE WHEN COALESCE(feb.feb_cnt, 0) = 0 THEN NULL
                ELSE (CAST(mar.mar_cnt AS REAL) - feb.feb_cnt) / feb.feb_cnt END AS pct_change
    FROM hubs h
    LEFT JOIN feb ON h.hub_id = feb.hub_id
    LEFT JOIN mar ON h.hub_id = mar.hub_id
)
SELECT hub_id, hub_name
FROM combined
WHERE pct_change > 0.20;