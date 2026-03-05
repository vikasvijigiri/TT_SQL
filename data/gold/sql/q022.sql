SELECT batch, blending, "compression",
       EXTRACT(EPOCH FROM ("compression" - blending)) / 3600 AS delay_hours
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE blending IS NOT NULL AND "compression" IS NOT NULL
ORDER BY delay_hours DESC
LIMIT 10