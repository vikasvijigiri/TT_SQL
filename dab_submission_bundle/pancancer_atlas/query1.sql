WITH "clinical_subset" AS (
  SELECT
    regexp_extract("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) AS barcode,
    "histological_type"
  FROM "pancancer_clinical_db"."clinical_info"
  WHERE "diagnosis" ILIKE '%LGG%'
    AND "histological_type" NOT LIKE '%[%]%'
    AND regexp_extract("Patient_description", '(TCGA-[A-Z0-9]+-[A-Z0-9]+)', 1) != ''
)
SELECT
  cs."histological_type",
  ROUND(AVG(LOG10(r."normalized_count" + 1)), 4) AS avg_log10_expression
FROM "clinical_subset" cs
JOIN "RNASeq_Expression" r
  ON r."ParticipantBarcode" = cs.barcode
WHERE r."Symbol" = 'IGF2'
  AND r."normalized_count" IS NOT NULL
GROUP BY cs."histological_type"
ORDER BY cs."histological_type";