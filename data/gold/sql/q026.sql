SELECT COUNT(*) AS pending_quality_batches
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE quality IS NULL