SELECT carrier, COUNT(*) FILTER (WHERE on_time = 0) * 1.0 / COUNT(*) AS otif_loss_rate
FROM "acme-chatbot".otif
GROUP BY carrier
ORDER BY otif_loss_rate DESC