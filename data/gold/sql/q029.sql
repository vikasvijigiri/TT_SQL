SELECT batch, fg_code, prod_desc
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE critical_sku = 'Yes' AND dispatch_date_time IS NULL