import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_PANCANCER_ATLAS\query_dataset'

conn = duckdb.connect(f'{base}/pancancer_clinical.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/pancancer_molecular.db' AS mol (TYPE duckdb)")

# How many BRCA patients who are alive?
print("=== BRCA alive patients ===")
brca = conn.execute("""
    SELECT COUNT(*) as cnt
    FROM clinical_info
    WHERE Patient_description ILIKE '%BRCA%' OR Patient_description ILIKE '%breast%'
""").fetchone()
print(f"  BRCA/breast patients: {brca[0]}")

alive = conn.execute("""
    SELECT COUNT(*) as cnt
    FROM clinical_info
    WHERE (Patient_description ILIKE '%BRCA%' OR Patient_description ILIKE '%breast%')
      AND Patient_description ILIKE '%Alive%'
""").fetchone()
print(f"  BRCA/breast alive patients: {alive[0]}")

# Sample BRCA patient description to understand vital status format
print("\n=== Sample BRCA patient descriptions ===")
sample = conn.execute("""
    SELECT Patient_description, histological_type
    FROM clinical_info
    WHERE Patient_description ILIKE '%breast%'
    LIMIT 3
""").fetchdf()
for _, row in sample.iterrows():
    print(f"  histological_type: {row['histological_type']}")
    print(f"  desc: {row['Patient_description'][:300]}")
    print()

# What does Patient_description look like for extracting patient_id?
print("=== Extract patient_id from Patient_description ===")
ids = conn.execute("""
    SELECT REGEXP_EXTRACT(Patient_description, 'patient (TCGA-[A-Z0-9-]+)', 1) AS patient_id_extracted,
           patient_id,
           histological_type,
           Patient_description
    FROM clinical_info
    WHERE Patient_description ILIKE '%breast%'
    LIMIT 5
""").fetchdf()
print(ids[['patient_id_extracted','patient_id','histological_type']].to_string())

# Check BRCA in Mutation_Data
print("\n=== CDH1 mutations sample ===")
cdh1 = conn.execute("""
    SELECT ParticipantBarcode, Hugo_Symbol, Variant_Classification
    FROM mol.Mutation_Data
    WHERE Hugo_Symbol = 'CDH1'
    LIMIT 5
""").fetchdf()
print(cdh1.to_string())
print(f"\nTotal CDH1 mutations: {conn.execute('SELECT COUNT(*) FROM mol.Mutation_Data WHERE Hugo_Symbol=chr(67)||chr(68)||chr(72)||chr(49)').fetchone()[0]}")

# Try joining clinical and molecular
print("\n=== Try joining ===")
join_test = conn.execute("""
    SELECT COUNT(*) as matched
    FROM clinical_info ci
    JOIN mol.Mutation_Data md ON md.ParticipantBarcode = REGEXP_EXTRACT(ci.Patient_description, 'patient (TCGA-[A-Z0-9-]+)', 1)
    WHERE md.Hugo_Symbol = 'CDH1'
    LIMIT 1
""").fetchone()
print(f"Joined CDH1 rows: {join_test[0]}")

# Try the full mutation rate query
print("\n=== CDH1 mutation rate by histological type for BRCA alive patients ===")
result = conn.execute("""
    WITH brca_alive AS (
        SELECT
            REGEXP_EXTRACT(Patient_description, 'patient (TCGA-[A-Z0-9-]+)', 1) AS patient_id_ext,
            histological_type
        FROM clinical_info
        WHERE Patient_description ILIKE '%breast%'
          AND Patient_description ILIKE '%Alive%'
    ),
    cdh1_mutated AS (
        SELECT DISTINCT ParticipantBarcode
        FROM mol.Mutation_Data
        WHERE Hugo_Symbol = 'CDH1'
    )
    SELECT
        ba.histological_type,
        COUNT(DISTINCT ba.patient_id_ext) AS total_patients,
        COUNT(DISTINCT cm.ParticipantBarcode) AS cdh1_patients,
        ROUND(100.0 * COUNT(DISTINCT cm.ParticipantBarcode) / COUNT(DISTINCT ba.patient_id_ext), 2) AS mutation_rate_pct
    FROM brca_alive ba
    LEFT JOIN cdh1_mutated cm ON cm.ParticipantBarcode = ba.patient_id_ext
    GROUP BY ba.histological_type
    HAVING COUNT(DISTINCT ba.patient_id_ext) > 0
    ORDER BY mutation_rate_pct DESC
    LIMIT 5
""").fetchdf()
print(result.to_string())

conn.close()
