WITH clinical_filtered AS (
    SELECT
        regexp_extract("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) AS barcode,
        "histological_type"
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "diagnosis" ILIKE '%LGG%'
      AND "histological_type" NOT LIKE '%[%]%'
      AND "Patient_description" IS NOT NULL
      AND regexp_extract("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) != ''
),
expression_filtered AS (
    SELECT
        "ParticipantBarcode" AS barcode,
        LOG10("normalized_count" + 1) AS log10_expr
    FROM "RNASeq_Expression"
    WHERE "Symbol" = 'IGF2'
      AND "normalized_count" IS NOT NULL
)
SELECT
    c."histological_type",
    ROUND(AVG(e.log10_expr), 4) AS avg_log10_expression
FROM clinical_filtered c
JOIN expression_filtered e ON c.barcode = e.barcode
GROUP BY c."histological_type"
ORDER BY c."histological_type";