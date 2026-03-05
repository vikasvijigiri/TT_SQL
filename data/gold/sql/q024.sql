SELECT batch, fg_code, prod_desc
FROM "acme-chatbot"."batch-and-packing-tracker"
WHERE rm_dispense IS NULL OR granulation IS NULL OR blending IS NULL OR "compression" IS NULL
   OR coating IS NULL OR imprinting IS NULL OR quality IS NULL OR packing IS NULL