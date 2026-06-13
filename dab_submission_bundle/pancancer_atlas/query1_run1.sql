WITH "clinical_barcode" AS (
    SELECT
        regexp_extract("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) AS barcode,
        "histological_type"
    FROM "clinical_info"
    WHERE "histological_type" NOT LIKE '%[%]%' -- exclude bracketed annotations
      AND regexp_extract("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) != ''
)
SELECT
    cb."histological_type",
    ROUND(AVG(LOG10(r."normalized_count" + 1)), 4) AS avg_log10_expression
FROM "clinical_barcode" cb
JOIN "RNASeq_Expression" r
  ON r."ParticipantBarcode" = cb.barcode
WHERE r."Symbol" = 'IGF2'
  AND r."normalized_count" IS NOT NULL
GROUP BY cb."histological_type"
ORDER BY cb."histological_type";