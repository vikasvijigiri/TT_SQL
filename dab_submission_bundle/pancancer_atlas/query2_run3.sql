WITH "clinical_patients" AS (
    SELECT
        REGEXP_EXTRACT("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) AS barcode,
        "histological_type"
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "diagnosis" = 'BRCA'
      AND ("days_to_death" IS NULL OR TRIM("days_to_death") = '')
      AND REGEXP_EXTRACT("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) != ''
),
"cdh1_patients" AS (
    SELECT DISTINCT "ParticipantBarcode" AS barcode
    FROM "Mutation_Data"
    WHERE "Hugo_Symbol" = 'CDH1'
),
"joined" AS (
    SELECT
        cp."histological_type",
        cp.barcode,
        CASE WHEN cd.barcode IS NOT NULL THEN 1 ELSE 0 END AS has_cdh1
    FROM "clinical_patients" cp
    LEFT JOIN "cdh1_patients" cd ON cp.barcode = cd.barcode
)
SELECT
    "histological_type",
    100.0 * SUM(has_cdh1)::DOUBLE / NULLIF(COUNT(DISTINCT barcode), 0)::DOUBLE AS pct_cdh1
FROM "joined"
GROUP BY "histological_type"
ORDER BY pct_cdh1 DESC
LIMIT 3;