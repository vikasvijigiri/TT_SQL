SELECT mat_category, AVG(dispense_qty) AS avg_dispense_qty
FROM "acme-chatbot"."material-packing-tracker"
GROUP BY mat_category