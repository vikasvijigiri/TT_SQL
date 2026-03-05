SELECT shipping_point, AVG(so_recp_to_act_shp_days) AS avg_days
FROM "acme-chatbot".otif
GROUP BY shipping_point