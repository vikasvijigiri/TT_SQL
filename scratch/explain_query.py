import sqlite3

db_path = 'C:/Users/VikasVijigiri/Documents/DataAgentBench/query_PATENTS/query_dataset/patent_publication.db'
cpc_path = 'C:/Users/VikasVijigiri/Documents/DataAgentBench/query_PATENTS/query_dataset/patent_CPCDefinition.db'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute(f"ATTACH DATABASE '{cpc_path}' AS patent_CPCDefinition_db;")
cur.execute("CREATE TEMP VIEW cpc_definition AS SELECT * FROM patent_CPCDefinition_db.cpc_definition;")

sql = """
WITH ordered_counts AS (
  SELECT
    cd.symbol AS cpc_code,
    CAST(substr(p.filing_date, 1, 4) AS INTEGER) AS filing_year,
    COUNT(*) AS filings,
    ROW_NUMBER() OVER (PARTITION BY cd.symbol ORDER BY CAST(substr(p.filing_date, 1, 4) AS INTEGER)) AS rn
  FROM publicationinfo p
  JOIN cpc_definition cd ON p.cpc = cd.symbol
  WHERE cd.level = 5
  GROUP BY cd.symbol, filing_year
),
ema_calc AS (
  SELECT
    cpc_code,
    filing_year,
    CAST(filings AS FLOAT) AS ema,
    rn
  FROM ordered_counts
  WHERE rn = 1
  UNION ALL
  SELECT
    oc.cpc_code,
    oc.filing_year,
    (0.2 * CAST(oc.filings AS FLOAT)) + (0.8 * ec.ema) AS ema,
    oc.rn
  FROM ordered_counts oc
  JOIN ema_calc ec ON oc.cpc_code = ec.cpc_code AND oc.rn = ec.rn + 1
),
best_year AS (
  SELECT
    cpc_code,
    filing_year,
    ema,
    ROW_NUMBER() OVER (PARTITION BY cpc_code ORDER BY ema DESC) AS rank_ema
  FROM ema_calc
)
SELECT cpc_code
FROM best_year
WHERE rank_ema = 1
  AND filing_year = 2022;
"""

try:
    print("Execution Plan:")
    for row in cur.execute("EXPLAIN QUERY PLAN " + sql).fetchall():
        print(row)
    
    print("\nChecking join count:")
    count = cur.execute("SELECT COUNT(*) FROM publicationinfo p JOIN cpc_definition cd ON p.cpc = cd.symbol").fetchone()[0]
    print("Direct join count:", count)
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
