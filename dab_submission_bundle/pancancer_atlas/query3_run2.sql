WITH patient_barcodes AS (
    SELECT DISTINCT
        "histological_type",
        regexp_extract("Patient_description", '(TCGA-[A-Z0-9-]+)', 1) AS barcode
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "tumor_tissue_site" = 'Breast'
      AND "histological_type" IS NOT NULL
      AND LOWER("Patient_description") LIKE '%female%'
      AND regexp_extract("Patient_description", '(TCGA-[A-Z0-9-]+)', 1) <> ''
),
cdh1_flags AS (
    SELECT "ParticipantBarcode" AS barcode,
           MAX(CASE WHEN "Hugo_Symbol" = 'CDH1' THEN 1 ELSE 0 END) AS has_cdh1
    FROM "Mutation_Data"
    WHERE "FILTER" = 'PASS'
    GROUP BY "ParticipantBarcode"
),
joined AS (
    SELECT p."histological_type",
           COALESCE(c.has_cdh1, 0) AS has_cdh1
    FROM patient_barcodes p
    LEFT JOIN cdh1_flags c ON p.barcode = c.barcode
),
contingency AS (
    SELECT "histological_type",
           has_cdh1,
           COUNT(*) AS obs
    FROM joined
    GROUP BY "histological_type", has_cdh1
),
margin AS (
    SELECT c.*, 
           SUM(c.obs) OVER (PARTITION BY c."histological_type") AS row_total,
           SUM(c.obs) OVER (PARTITION BY c.has_cdh1) AS col_total,
           SUM(c.obs) OVER () AS grand_total
    FROM contingency c
),
filtered AS (
    SELECT *
    FROM margin
    WHERE row_total > 10 AND col_total > 10
)
SELECT SUM(
           POWER(obs - (row_total * col_total / NULLIF(grand_total, 0)), 2) /
           NULLIF(row_total * col_total / NULLIF(grand_total, 0), 0)
       ) AS chi_square
FROM filtered;