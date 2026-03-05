SELECT
    ship_to_region,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN on_time_in_full_loss != 0 THEN 1 ELSE 0 END) AS otif_losses,
    ROUND(
        100.0 * SUM(CASE WHEN on_time_in_full_loss != 0 THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS otif_loss_percentage
FROM
    "acme-chatbot".otif
WHERE
    on_time_in_full_loss IS NOT NULL
    AND ship_to_region IS NOT NULL
GROUP BY
    ship_to_region
ORDER BY
    otif_loss_percentage DESC