SELECT component, component_name, (stock - required_qty) AS excess_stock
FROM "acme-chatbot"."material-packing-tracker"
ORDER BY excess_stock DESC
LIMIT 10