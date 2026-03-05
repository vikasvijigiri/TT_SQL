SELECT equipment_name, SUM(batch) AS total_batch
FROM "acme-chatbot"."manufacturing-tracker"
WHERE startedrecorded_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY equipment_name