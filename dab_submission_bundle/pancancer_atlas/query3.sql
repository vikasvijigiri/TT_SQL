WITH "clinical_filtered" AS (
    SELECT 
        regexp_extract("Patient_description", '(TCGA-[A-Z0-9-]+)', 1) AS "patient_barcode",
        "histological_type"
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "Patient_description" ILIKE '%female%'
      AND "tumor_tissue_site" ILIKE '%Breast%'
      AND "histological_type" IS NOT NULL
),
"cdh1_flags" AS (
    SELECT 
        "ParticipantBarcode" AS "patient_barcode",
        MAX(CASE WHEN "Hugo_Symbol" = 'CDH1' AND "FILTER" = 'PASS' THEN 1 ELSE 0 END) AS "has_cdh1"
    FROM "Mutation_Data"
    GROUP BY "ParticipantBarcode"
),
"joined" AS (
    SELECT 
        cf."histological_type",
        COALESCE(cf2."has_cdh1", 0) AS "has_cdh1",
        cf."patient_barcode"
    FROM "clinical_filtered" cf
    LEFT JOIN "cdh1_flags" cf2
        ON cf."patient_barcode" = cf2."patient_barcode"
),
"contingency" AS (
    SELECT 
        "histological_type",
        "has_cdh1",
        COUNT(DISTINCT "patient_barcode") AS "obs"
    FROM "joined"
    GROUP BY "histological_type", "has_cdh1"
),
"marginals" AS (
    SELECT 
        c.*, 
        SUM(c."obs") OVER (PARTITION BY c."histological_type") AS "row_total",
        SUM(c."obs") OVER (PARTITION BY c."has_cdh1") AS "col_total",
        SUM(c."obs") OVER () AS "grand_total"
    FROM "contingency" c
),
"filtered" AS (
    SELECT *
    FROM "marginals"
    WHERE "row_total" > 10 AND "col_total" > 10
)
SELECT SUM(
           POWER("obs" - ("row_total" * "col_total" / NULLIF("grand_total", 0)), 2) /
           NULLIF(("row_total" * "col_total" / NULLIF("grand_total", 0)), 0)
       )::DOUBLE AS "chi_square"
FROM "filtered";