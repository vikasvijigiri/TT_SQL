SELECT batch, fg_code, prod_desc
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE dispatch_date_time IS NOT NULL AND receipt_at_ev_date_time IS NULL