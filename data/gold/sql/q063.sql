SELECT 
    component,
    component_name,
    fg_code,
    required_qty,
    stock,
    (required_qty - stock) AS shortage_qty,
    status,
    mat_category
FROM 
    "acme-chatbot"."material-packing-tracker"
WHERE 
    shortage_flag = 'Yes'
    OR (stock IS NOT NULL AND required_qty IS NOT NULL AND stock < required_qty)
ORDER BY 
    shortage_qty DESC NULLS LAST