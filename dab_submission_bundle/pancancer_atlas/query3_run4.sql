WITH "clinical" AS (
    SELECT
        regexp_extract("Patient_description", '(TCGA-[A-Z0-9-]+)', 1) AS patient_id,
        "histological_type"
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "tumor_tissue_site" ILIKE '%Breast%'
      AND LOWER("Patient_description") LIKE '%female%'
      AND "histological_type" IS NOT NULL
),
"cdh1_flags" AS (
    SELECT
        "ParticipantBarcode" AS patient_id,
        MAX(CASE WHEN "Hugo_Symbol" = 'CDH1' THEN 1 ELSE 0 END) AS has_cdh1
    FROM "Mutation_Data"
    WHERE "FILTER" = 'PASS'
    GROUP BY "ParticipantBarcode"
),
"joined" AS (
    SELECT
        c."histological_type",
        COALESCE(f.has_cdh1, 0) AS has_cdh1
    FROM "clinical" c
    LEFT JOIN "cdh1_flags" f ON c.patient_id = f.patient_id
),
"contingency" AS (
    SELECT
        "histological_type",
        has_cdh1,
        COUNT(*) AS obs
    FROM "joined"
    GROUP BY "histological_type", has_cdh1
),
"marginals" AS (
    SELECT
        c.*,
        SUM(obs) OVER (PARTITION BY "histological_type") AS row_total,
        SUM(obs) OVER (PARTITION BY has_cdh1) AS col_total,
        SUM(obs) OVER () AS grand_total
    FROM "contingency" c
),
"filtered" AS (
    SELECT *
    FROM "marginals"
    WHERE row_total > 10 AND col_total > 10
)
SELECT SUM(
           POWER(obs - (row_total * col_total / NULLIF(grand_total, 0)), 2) /
           NULLIF(row_total * col_total / NULLIF(grand_total, 0), 0)
       ) AS chi_square
FROM "filtered";