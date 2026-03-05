SELECT shipping_point, AVG(del_to_act_shp_days) AS avg_delay_days
FROM "acme-chatbot".otif
where shipping_point is not null
GROUP BY shipping_point
ORDER BY avg_delay_days DESC