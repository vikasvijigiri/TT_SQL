SELECT 
    material,
    material_desc,
    ROUND(AVG(on_time_in_full_loss::bigint), 2) AS avg_otif_score
FROM 
    "acme-chatbot".otif
WHERE 
    TO_DATE(reporting_date, 'YYYY-MM-DD') >= CURRENT_DATE - INTERVAL '60 days'
GROUP BY 
    material, material_desc
HAVING 
    AVG(on_time_in_full_loss) < 0.8
ORDER BY 
    avg_otif_score ASC