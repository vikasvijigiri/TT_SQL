SELECT material, prod_desc, month1_demand as current_demand,month2_demand,month3_demand,month4_demand
FROM "acme-chatbot".doh
ORDER BY month1_demand DESC
LIMIT 10