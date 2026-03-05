SELECT 
  DATE(dispatch_date_time) AS dispatch_date,
  COUNT(*) AS batches_dispatched
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE dispatch_date_time IS NOT NULL
GROUP BY dispatch_date
ORDER BY dispatch_date DESC