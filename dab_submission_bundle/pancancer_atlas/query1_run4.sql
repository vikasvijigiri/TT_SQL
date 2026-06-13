WITH "ci_clean" AS (
    SELECT
        "histological_type",
        REGEXP_EXTRACT("Patient_description", '(TCGA-[0-9]{2}-[0-9]{4})') AS barcode
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "diagnosis" = 'LGG'
      AND "histological_type" NOT LIKE '%[%]%'
      AND REGEXP_EXTRACT("Patient_description", '(TCGA-[0-9]{2}-[0-9]{4})') != ''
)
SELECT
    ci_clean."histological_type",
    ROUND(AVG(LOG10(rse."normalized_count" + 1)), 4) AS avg_log10_expression
FROM "ci_clean" ci_clean
JOIN "RNASeq_Expression" rse
    ON ci_clean.barcode = rse."ParticipantBarcode"
WHERE rse."Symbol" = 'IGF2'
  AND rse."normalized_count" IS NOT NULL
GROUP BY ci_clean."histological_type"
ORDER BY avg_log10_expression DESC;