WITH filtered_tasks AS (
    SELECT t."WhatId", t."Subject"
    FROM "activities_db"."Task" t
    WHERE REPLACE(t."WhatId", '#', '') = '006Wt000007BGGjIAO'
),
task_counts AS (
    SELECT
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t."Subject", ''))) LIKE '%qualification%' THEN 1 ELSE 0 END) AS qual_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t."Subject", ''))) LIKE '%discovery%' THEN 1 ELSE 0 END) AS disc_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t."Subject", ''))) LIKE '%quote%' THEN 1 ELSE 0 END) AS quote_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t."Subject", ''))) LIKE '%negotiation%' THEN 1 ELSE 0 END) AS nego_cnt,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(t."Subject", ''))) LIKE '%closed%' THEN 1 ELSE 0 END) AS closed_cnt
    FROM filtered_tasks t
),
op_stage AS (
    SELECT TRIM(o."StageName") AS stage_name
    FROM "sales_pipeline"."Opportunity" o
    WHERE REPLACE(o."Id", '#', '') = '006Wt000007BGGjIAO'
)
SELECT CASE
    WHEN tc.qual_cnt > 0 THEN 'Qualification'
    WHEN tc.disc_cnt > 0 THEN 'Discovery'
    WHEN tc.quote_cnt > 0 THEN 'Quote'
    WHEN tc.nego_cnt > 0 THEN 'Negotiation'
    WHEN tc.closed_cnt > 0 THEN 'Closed'
    ELSE os.stage_name
END AS correct_stage
FROM task_counts tc CROSS JOIN op_stage os;