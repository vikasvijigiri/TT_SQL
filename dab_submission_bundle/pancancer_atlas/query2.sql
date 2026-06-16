WITH "clinical_bc" AS (
    SELECT
        REGEXP_EXTRACT("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) AS barcode,
        "histological_type"
    FROM "clinical_info"
    WHERE ("diagnosis" ILIKE '%BRCA%' OR "diagnosis" ILIKE '%Breast%')
      AND "Patient_description" ILIKE '%Alive%'
      AND REGEXP_EXTRACT("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) <> ''
),
"cdh1_patients" AS (
    SELECT DISTINCT "ParticipantBarcode" AS barcode
    FROM "Mutation_Data"
    WHERE "Hugo_Symbol" = 'CDH1'
)
SELECT
    cb."histological_type",
    100.0 * COUNT(DISTINCT cdh1.barcode)::DOUBLE / NULLIF(COUNT(DISTINCT cb.barcode)::DOUBLE, 0) AS pct_cdh1
FROM "clinical_bc" cb
LEFT JOIN "cdh1_patients" cdh1 ON cdh1.barcode = cb.barcode
GROUP BY cb."histological_type"
ORDER BY pct_cdh1 DESC
LIMIT 3;