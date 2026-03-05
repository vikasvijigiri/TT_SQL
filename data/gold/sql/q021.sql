SELECT 
  ROUND(AVG(EXTRACT(EPOCH FROM (dispatch_date_time - rm_dispense)) / 3600), 2) AS avg_hours_rm_to_dispatch
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE rm_dispense IS NOT NULL AND dispatch_date_time IS NOT NULL