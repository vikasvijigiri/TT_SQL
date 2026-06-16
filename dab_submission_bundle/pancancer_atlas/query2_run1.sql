WITH "clinical_barcode" AS (
    SELECT
        "histological_type",
        REGEXP_EXTRACT("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) AS barcode
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "icd_o_3_site" = 'C50'
      AND ("days_to_death" IS NULL OR "days_to_death" = '')
),
"cdh1_patients" AS (
    SELECT DISTINCT "ParticipantBarcode" AS barcode
    FROM "Mutation_Data"
    WHERE "Hugo_Symbol" = 'CDH1'
),
"joined" AS (
    SELECT
        cb."histological_type",
        cb.barcode,
        CASE WHEN cp.barcode IS NOT NULL THEN 1 ELSE 0 END AS has_cdh1
    FROM "clinical_barcode" cb
    LEFT JOIN "cdh1_patients" cp ON cp.barcode = cb.barcode
    WHERE cb.barcode IS NOT NULL
)
SELECT
    "histological_type",
    100.0 * SUM(has_cdh1)::DOUBLE / NULLIF(COUNT(DISTINCT barcode), 0)::DOUBLE AS pct_cdh1
FROM "joined"
GROUP BY "histological_type"
ORDER BY pct_cdh1 DESC
LIMIT 3;