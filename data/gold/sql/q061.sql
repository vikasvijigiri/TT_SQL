WITH top10_skus AS (
    SELECT 
        material,
        prod_desc,
        SUM(demand_3m) AS total_3m_demand
    FROM 
        "acme-chatbot"."demand-forecast"
    GROUP BY 
        material, prod_desc
    ORDER BY 
        total_3m_demand DESC
    LIMIT 10
),
weekly_demand AS (
    SELECT 
        df.material,
        df.prod_desc,
        DATE_TRUNC('week', df.month) AS week_start,
        SUM(df.demand) AS weekly_demand
    FROM 
        "acme-chatbot"."demand-forecast" df
    JOIN 
        top10_skus t10 ON df.material = t10.material
    GROUP BY 
        df.material, df.prod_desc, DATE_TRUNC('week', df.month)
)
SELECT 
    material,
    prod_desc,
    week_start,
    weekly_demand
FROM 
    weekly_demand
ORDER BY 
    week_start ASC, weekly_demand DESC