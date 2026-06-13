WITH task_counts AS (
    SELECT
        o.Id AS opportunity_id,
        TRIM(o.StageName) AS original_stage,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t.Subject, ''))) LIKE '%qualification%' THEN 1 ELSE 0 END) AS qual_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t.Subject, ''))) LIKE '%discovery%' THEN 1 ELSE 0 END) AS disc_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t.Subject, ''))) LIKE '%quote%' THEN 1 ELSE 0 END) AS quote_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t.Subject, ''))) LIKE '%negotiation%' THEN 1 ELSE 0 END) AS nego_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t.Subject, ''))) LIKE '%closed%' THEN 1 ELSE 0 END) AS closed_cnt
    FROM "sales_pipeline"."Opportunity" o
    LEFT JOIN "activities_db"."Task" t ON t.WhatId = o.Id
    WHERE o.Id = '006Wt000007BGGjIAO'
    GROUP BY o.Id, o.StageName
)
SELECT CASE
    WHEN qual_cnt > 0 THEN 'Qualification'
    WHEN disc_cnt > 0 THEN 'Discovery'
    WHEN quote_cnt > 0 THEN 'Quote'
    WHEN nego_cnt > 0 THEN 'Negotiation'
    WHEN closed_cnt > 0 THEN 'Closed'
    ELSE original_stage
END AS correct_stage
FROM task_counts;