SELECT blending_code, SUM(dispense_qty) AS total_dispense
FROM "acme-chatbot"."material-packing-tracker"
GROUP BY blending_code
ORDER BY total_dispense DESC
LIMIT 10