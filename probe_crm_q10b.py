import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'
conn = duckdb.connect(f'{base}/sales_pipeline.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/support.db' AS support_db (TYPE sqlite)")

# Check Field__c distinct values
vals = conn.execute('SELECT DISTINCT "Field__c" FROM support_db."CaseHistory__c" LIMIT 30').fetchdf()
print("Field__c values:")
print(vals.to_string())

# Count by Field__c
cnt = conn.execute('''
    SELECT "Field__c", COUNT(*) as cnt
    FROM support_db."CaseHistory__c"
    GROUP BY "Field__c"
    ORDER BY cnt DESC
    LIMIT 20
''').fetchdf()
print("\nField__c counts:")
print(cnt.to_string())

# Sample the Owner Assignment filter
oa = conn.execute('''
    SELECT COUNT(*) FROM support_db."CaseHistory__c"
    WHERE "Field__c" = 'Owner Assignment'
''').fetchone()
print(f"\nOwner Assignment count: {oa[0]}")

owner = conn.execute('''
    SELECT COUNT(*) FROM support_db."CaseHistory__c"
    WHERE "Field__c" = 'Owner'
''').fetchone()
print(f"Owner count: {owner[0]}")

conn.close()
