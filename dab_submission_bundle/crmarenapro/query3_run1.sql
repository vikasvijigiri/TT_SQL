WITH "target_opportunity" AS (
    SELECT REPLACE(TRIM("Id"), '#', '') AS opp_id,
           TRIM("StageName") AS current_stage
    FROM "sales_pipeline"."Opportunity"
    WHERE REPLACE(TRIM("Id"), '#', '') = REPLACE(TRIM('006Wt000007BGGjIAO'), '#', '')
), "task_counts" AS (
    SELECT o.opp_id,
           SUM(CASE WHEN LOWER(COALESCE(t."Subject", '')) LIKE '%qualification%' THEN 1 ELSE 0 END) AS qual_cnt,
           SUM(CASE WHEN LOWER(COALESCE(t."Subject", '')) LIKE '%discovery%' THEN 1 ELSE 0 END) AS disc_cnt,
           SUM(CASE WHEN LOWER(COALESCE(t."Subject", '')) LIKE '%quote%' THEN 1 ELSE 0 END) AS quote_cnt,
           SUM(CASE WHEN LOWER(COALESCE(t."Subject", '')) LIKE '%negotiation%' THEN 1 ELSE 0 END) AS nego_cnt,
           SUM(CASE WHEN LOWER(COALESCE(t."Subject", '')) LIKE '%closed%' THEN 1 ELSE 0 END) AS closed_cnt,
           o.current_stage
    FROM "target_opportunity" o
    LEFT JOIN "activities_db"."Task" t
      ON REPLACE(TRIM(t."WhatId"), '#', '') = o.opp_id
    GROUP BY o.opp_id, o.current_stage
)
SELECT CASE
         WHEN qual_cnt > 0 THEN 'Qualification'
         WHEN disc_cnt > 0 THEN 'Discovery'
         WHEN quote_cnt > 0 THEN 'Quote'
         WHEN nego_cnt > 0 THEN 'Negotiation'
         WHEN closed_cnt > 0 THEN 'Closed'
         ELSE TRIM(current_stage)
       END AS correct_stage
FROM "task_counts";