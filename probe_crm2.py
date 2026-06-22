import sqlite3, duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'

# Check OrderItem columns and data
conn = sqlite3.connect(f'{base}/products_orders.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info('OrderItem')")
oi_cols = [c[1] for c in cursor.fetchall()]
print("OrderItem columns:", oi_cols)
cursor.execute("SELECT * FROM OrderItem LIMIT 3")
print("OrderItem sample:", cursor.fetchall())

# Find OrderItems for product 01tWt000006hV8LIAU
cursor.execute("SELECT Id, Product2Id FROM OrderItem WHERE Product2Id='01tWt000006hV8LIAU' LIMIT 5")
matching_ois = cursor.fetchall()
print(f"\nOrderItems for product 01tWt000006hV8LIAU: {matching_ois}")
conn.close()

# Check Case and CaseHistory
conn2 = sqlite3.connect(f'{base}/support.db')
cursor2 = conn2.cursor()

# Check Case for the product via OrderItem join
oi_ids = [oi[0] for oi in matching_ois] if matching_ois else []
if oi_ids:
    placeholders = ','.join(['?' for _ in oi_ids])
    cursor2.execute(f"""
        SELECT c.IssueId__c, COUNT(*) as cnt
        FROM "Case" c
        WHERE c.OrderItemId__c IN ({placeholders})
          AND c.CreatedDate >= '2022-08-16'
          AND c.CreatedDate < '2023-01-16'
          AND c.IssueId__c IS NOT NULL
        GROUP BY c.IssueId__c
        ORDER BY cnt DESC
        LIMIT 5
    """, oi_ids)
    issue_counts = cursor2.fetchall()
    print(f"\nIssue counts for product cases: {issue_counts}")

    # The expected answer is a03Wt00000JqnHwIAJ
    cursor2.execute("SELECT * FROM Issue__c WHERE Id=?", ('a03Wt00000JqnHwIAJ',))
    issue = cursor2.fetchone()
    print(f"\nExpected issue a03Wt00000JqnHwIAJ: {issue}")
else:
    print("\nNo matching OrderItems found! Trying without product filter...")
    # Check Case.OrderItemId__c format
    cursor2.execute("SELECT Id, OrderItemId__c, IssueId__c, CreatedDate FROM 'Case' LIMIT 5")
    print("Case sample:", cursor2.fetchall())

# Check CaseHistory__c for q10
print("\n=== CaseHistory for q10 ===")
cursor2.execute("SELECT DISTINCT Field__c FROM CaseHistory__c LIMIT 20")
fields = cursor2.fetchall()
print("Distinct Field__c values:", [f[0] for f in fields])

cursor2.execute("""
    SELECT CaseId__c, Field__c, OldValue__c, NewValue__c, CreatedDate
    FROM CaseHistory__c
    WHERE Field__c = 'Owner Assignment'
    LIMIT 5
""")
owner_hist = cursor2.fetchall()
print("\nOwner Assignment CaseHistory:", owner_hist[:3])

conn2.close()
