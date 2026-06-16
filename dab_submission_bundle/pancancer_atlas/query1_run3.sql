WITH "clinical" AS (
    SELECT
        regexp_extract("Patient_description", '(TCGA-[0-9]{2}-[0-9]{4})', 1) AS barcode,
        "histological_type"
    FROM "pancancer_clinical_db"."clinical_info"
    WHERE "diagnosis" ILIKE '%LGG%'
      AND "histological_type" NOT LIKE '%[%]%'
      AND regexp_extract("Patient_description", '(TCGA-[0-9]{2}-[0-9]{4})', 1) != ''
), "expr" AS (
    SELECT "ParticipantBarcode", "normalized_count"
    FROM "RNASeq_Expression"
    WHERE "Symbol" = 'IGF2'
      AND "normalized_count" IS NOT NULL
)
SELECT
    "clinical"."histological_type",
    ROUND(AVG(LOG10("expr"."normalized_count" + 1)), 4) AS "avg_log10_expression"
FROM "clinical"
JOIN "expr" ON "clinical".barcode = "expr"."ParticipantBarcode"
GROUP BY "clinical"."histological_type"
ORDER BY "avg_log10_expression" DESC;