import sqlite3, duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'

# Check CaseHistory__c Field__c values
conn = duckdb.connect(f'{base}/sales_pipeline.duckdb', read_only=True)
conn.execute("LOAD sqlite")

# Find sibling DBs
import os
dbs = [f for f in os.listdir(base) if f.endswith(('.db','.sqlite','.duckdb')) and f != 'sales_pipeline.duckdb']
print(f"Sibling DBs: {dbs}")
for db in dbs:
    ext = 'sqlite' if db.endswith(('.db','.sqlite')) else 'duckdb'
    alias = db.replace('.','_').replace('-','_')
    try:
        if ext == 'sqlite':
            conn.execute(f"ATTACH IF NOT EXISTS '{base}/{db}' AS {alias} (TYPE sqlite)")
        else:
            conn.execute(f"ATTACH IF NOT EXISTS '{base}/{db}' AS {alias}")
        print(f"Attached: {db} as {alias}")
    except Exception as e:
        print(f"Error attaching {db}: {e}")

# Show all tables
tabs = conn.execute("SHOW ALL TABLES").fetchdf()
print("\nAll tables:")
print(tabs[['schema','name']].to_string())

# Find CaseHistory table
ch_tables = [r for _, r in tabs.iterrows() if 'case' in r['name'].lower()]
print(f"\nCase-related tables: {[(r['schema'], r['name']) for _, r in tabs.iterrows() if 'case' in r['name'].lower()]}")

# Check Field__c values
for _, row in tabs.iterrows():
    if 'CaseHistory' in row['name'] or 'casehistory' in row['name'].lower():
        schema = row['schema']
        name = row['name']
        print(f"\nChecking {schema}.{name}:")
        try:
            vals = conn.execute(f'SELECT DISTINCT "Field__c" FROM "{schema}"."{name}" LIMIT 20').fetchdf()
            print(vals.to_string())
        except Exception as e:
            print(f"  Error: {e}")

conn.close()
