WITH "clinical" AS (
    SELECT
        regexp_extract("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) AS barcode,
        "histological_type"
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE lower("Patient_description") LIKE '%female%'
      AND ("tumor_tissue_site" ILIKE '%breast%' OR "tumor_tissue_site" ILIKE '%brca%')
      AND "histological_type" IS NOT NULL
),
"cdh1_flags" AS (
    SELECT
        "ParticipantBarcode" AS barcode,
        MAX(CASE WHEN "Hugo_Symbol" = 'CDH1' AND "FILTER" = 'PASS' THEN 1 ELSE 0 END) AS has_cdh1
    FROM "Mutation_Data"
    GROUP BY "ParticipantBarcode"
),
"joined" AS (
    SELECT
        c."histological_type",
        COALESCE(f.has_cdh1, 0) AS has_cdh1,
        c.barcode
    FROM "clinical" c
    LEFT JOIN "cdh1_flags" f ON c.barcode = f.barcode
),
"contingency" AS (
    SELECT
        "histological_type",
        has_cdh1,
        COUNT(DISTINCT barcode) AS obs
    FROM "joined"
    GROUP BY "histological_type", has_cdh1
),
"marginals" AS (
    SELECT
        "histological_type",
        has_cdh1,
        obs,
        SUM(obs) OVER (PARTITION BY "histological_type") AS row_total,
        SUM(obs) OVER (PARTITION BY has_cdh1) AS col_total,
        SUM(obs) OVER () AS grand_total
    FROM "contingency"
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