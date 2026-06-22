import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_PANCANCER_ATLAS\query_dataset'
conn = duckdb.connect(f'{base}/pancancer_clinical.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/pancancer_molecular.db' AS mol (TYPE duckdb)")

# Test direct TCGA barcode extraction (no 'patient' prefix needed)
print("=== Direct TCGA barcode extraction ===")
test = conn.execute("""
    SELECT
        REGEXP_EXTRACT(Patient_description, 'TCGA-[A-Z0-9-]+', 0) AS patient_barcode,
        patient_id,
        histological_type,
        LEFT(Patient_description, 150) AS desc_excerpt
    FROM clinical_info
    WHERE Patient_description ILIKE '%breast%'
    LIMIT 8
""").fetchdf()
print(test.to_string())

# Count how many BRCA alive patients we can extract a barcode for
print("\n=== Coverage of barcode extraction ===")
coverage = conn.execute("""
    SELECT
        COUNT(*) as total_brca_alive,
        COUNT(CASE WHEN REGEXP_EXTRACT(Patient_description, 'TCGA-[A-Z0-9-]+', 0) != '' THEN 1 END) as with_barcode
    FROM clinical_info
    WHERE Patient_description ILIKE '%breast%'
      AND Patient_description ILIKE '%Alive%'
""").fetchone()
print(f"Total BRCA alive: {coverage[0]}, with extractable barcode: {coverage[1]}")

# Run the full CDH1 mutation rate query with direct TCGA extraction
print("\n=== CDH1 mutation rate (fixed join) ===")
result = conn.execute("""
    WITH brca_alive AS (
        SELECT
            REGEXP_EXTRACT(Patient_description, 'TCGA-[A-Z0-9-]+', 0) AS barcode,
            histological_type
        FROM clinical_info
        WHERE Patient_description ILIKE '%breast%'
          AND Patient_description ILIKE '%Alive%'
          AND REGEXP_EXTRACT(Patient_description, 'TCGA-[A-Z0-9-]+', 0) != ''
    ),
    cdh1_mutated AS (
        SELECT DISTINCT ParticipantBarcode
        FROM mol.Mutation_Data
        WHERE Hugo_Symbol = 'CDH1'
    )
    SELECT
        ba.histological_type,
        COUNT(DISTINCT ba.barcode) AS total_patients,
        COUNT(DISTINCT cm.ParticipantBarcode) AS cdh1_patients,
        ROUND(100.0 * COUNT(DISTINCT cm.ParticipantBarcode) / NULLIF(COUNT(DISTINCT ba.barcode), 0), 2) AS mutation_rate_pct
    FROM brca_alive ba
    LEFT JOIN cdh1_mutated cm ON cm.ParticipantBarcode = ba.barcode
    GROUP BY ba.histological_type
    HAVING COUNT(DISTINCT ba.barcode) > 0
    ORDER BY mutation_rate_pct DESC
    LIMIT 5
""").fetchdf()
print(result.to_string())

conn.close()
