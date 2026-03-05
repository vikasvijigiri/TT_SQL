SELECT COUNT(*) AS in_progress_batches
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE dispatch_date_time IS NULL