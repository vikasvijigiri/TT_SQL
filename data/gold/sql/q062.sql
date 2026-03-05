SELECT 
    component,
    component_name,
    priority,
    SUM(dispense_qty) AS total_dispensed,
    SUM(demand_qty) AS total_demand,
    (SUM(demand_qty) - SUM(dispense_qty)) AS dispense_gap
FROM 
    "acme-chatbot"."material-packing-tracker"
WHERE 
    priority IS NOT NULL
    AND demand_qty IS NOT NULL
    AND dispense_qty IS NOT NULL
GROUP BY 
    component, component_name, priority
HAVING 
    (SUM(demand_qty) - SUM(dispense_qty)) > 0
ORDER BY 
    priority ASC,
    dispense_gap DESC
LIMIT 10