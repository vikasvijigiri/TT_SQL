WITH wholesale AS (
    SELECT 
        strftime('%Y', w.whsle_date) AS year,
        c.category_name,
        ROUND(AVG(w."whsle_px_rmb-kg"), 2) AS avg_wholesale_price,
        ROUND(MAX(w."whsle_px_rmb-kg"), 2) AS max_wholesale_price,
        ROUND(MIN(w."whsle_px_rmb-kg"), 2) AS min_wholesale_price,
        ROUND(MAX(w."whsle_px_rmb-kg") - MIN(w."whsle_px_rmb-kg"), 2) AS wholesale_price_diff,
        ROUND(SUM(w."whsle_px_rmb-kg"), 2) AS total_wholesale_price
    FROM veg_whsle_df w
    JOIN veg_cat c ON w.item_code = c.item_code
    WHERE strftime('%Y', w.whsle_date) BETWEEN '2020' AND '2023'
    GROUP BY year, c.category_name
),
selling AS (
    SELECT 
        strftime('%Y', t.txn_date) AS year,
        c.category_name,
        ROUND(SUM(t."unit_selling_px_rmb/kg" * t."qty_sold(kg)"), 2) AS total_selling_price
    FROM veg_txn_df t
    JOIN veg_cat c ON t.item_code = c.item_code
    WHERE strftime('%Y', t.txn_date) BETWEEN '2020' AND '2023'
    GROUP BY year, c.category_name
),
loss AS (
    SELECT 
        strftime('%Y', w.whsle_date) AS year,
        c.category_name,
        ROUND(AVG(l."loss_rate_%"), 2) AS avg_loss_rate,
        ROUND(SUM(w."whsle_px_rmb-kg" * l."loss_rate_%" / 100.0), 2) AS total_loss
    FROM veg_whsle_df w
    JOIN veg_cat c ON w.item_code = c.item_code
    JOIN veg_loss_rate_df l ON w.item_code = l.item_code
    WHERE strftime('%Y', w.whsle_date) BETWEEN '2020' AND '2023'
    GROUP BY year, c.category_name
)
SELECT 
    w.year,
    w.category_name,
    w.avg_wholesale_price,
    w.max_wholesale_price,
    w.min_wholesale_price,
    w.wholesale_price_diff,
    w.total_wholesale_price,
    s.total_selling_price,
    l.avg_loss_rate,
    l.total_loss,
    ROUND(s.total_selling_price - w.total_wholesale_price, 2) AS profit
FROM wholesale w
LEFT JOIN selling s ON w.year = s.year AND w.category_name = s.category_name
LEFT JOIN loss l ON w.year = l.year AND w.category_name = l.category_name
ORDER BY w.year, w.category_name;