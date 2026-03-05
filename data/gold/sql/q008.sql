SELECT 
  otif_loss_f1,
  COUNT(*) AS occurrences,
  ROUND(AVG(on_time_in_full_loss::int), 2) AS avg_otif
FROM "acme-chatbot".otif
WHERE otif_loss_f1 IS NOT NULL
GROUP BY otif_loss_f1
ORDER BY occurrences DESC