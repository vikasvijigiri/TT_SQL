SELECT COUNT(*) AS demand_gt_dispense
FROM "acme-chatbot"."material-packing-tracker"
WHERE demand_qty > dispense_qty