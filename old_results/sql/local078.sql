WITH MaxComposition AS (
    SELECT 
        im.interest_id, 
        im.month_year, 
        im.composition, 
        imap.interest_name,
        ROW_NUMBER() OVER (PARTITION BY im.interest_id ORDER BY im.composition DESC) as rn
    FROM 
        interest_metrics im
    JOIN 
        interest_map imap ON im.interest_id = imap.id
),
TopBottomCompositions AS (
    SELECT 
        month_year, 
        interest_name, 
        composition
    FROM 
        MaxComposition
    WHERE 
        rn = 1
)
SELECT 
    month_year, 
    interest_name, 
    composition
FROM 
    TopBottomCompositions
ORDER BY 
    composition DESC
LIMIT 10
UNION ALL
SELECT 
    month_year, 
    interest_name, 
    composition
FROM 
    TopBottomCompositions
ORDER BY 
    composition ASC
LIMIT 10;