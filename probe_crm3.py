import sqlite3

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'

# Deep dive on CRM q5
conn_po = sqlite3.connect(f'{base}/products_orders.db')
conn_sup = sqlite3.connect(f'{base}/support.db')

cur_po = conn_po.cursor()
cur_sup = conn_sup.cursor()

# Get ALL OrderItem IDs for product
cur_po.execute("SELECT Id FROM OrderItem WHERE Product2Id='01tWt000006hV8LIAU'")
oi_ids_raw = [r[0] for r in cur_po.fetchall()]
print(f"OrderItem IDs for product (raw): {oi_ids_raw}")

# Normalize IDs (strip # and whitespace)
oi_ids_clean = [oid.strip().lstrip('#') for oid in oi_ids_raw]
print(f"OrderItem IDs (cleaned): {oi_ids_clean}")

# Check Cases that point to these OrderItems
cur_sup.execute("SELECT COUNT(*) FROM 'Case'")
print(f"\nTotal cases: {cur_sup.fetchone()[0]}")

# Check Case.OrderItemId__c values
cur_sup.execute("SELECT Id, OrderItemId__c, IssueId__c, CreatedDate FROM 'Case' WHERE OrderItemId__c IS NOT NULL LIMIT 10")
print("Cases with OrderItemId__c:")
for row in cur_sup.fetchall():
    print(f"  {row}")

# Try without date filter
cur_sup.execute("""
    SELECT c.IssueId__c, COUNT(*) as cnt
    FROM "Case" c
    WHERE (c.OrderItemId__c IN ({}) OR
           REPLACE(c.OrderItemId__c, '#', '') IN ({}))
    AND c.IssueId__c IS NOT NULL
    GROUP BY c.IssueId__c
    ORDER BY cnt DESC
    LIMIT 5
""".format(
    ','.join(f"'{x}'" for x in oi_ids_raw + oi_ids_clean),
    ','.join(f"'{x}'" for x in oi_ids_clean)
))
results = cur_sup.fetchall()
print(f"\nCases matched (no date filter): {results}")

# Check all cases for the date window
cur_sup.execute("""
    SELECT Id, OrderItemId__c, IssueId__c, CreatedDate
    FROM "Case"
    WHERE CreatedDate >= '2022-08-16' AND CreatedDate < '2023-01-16'
    LIMIT 10
""")
print("\nCases in date range:")
for row in cur_sup.fetchall():
    print(f"  {row}")

# Cross-reference: check if case OrderItemId__c matches via normalized IDs
cur_sup.execute("SELECT DISTINCT OrderItemId__c FROM 'Case' WHERE OrderItemId__c IS NOT NULL LIMIT 20")
case_oi_ids = [r[0] for r in cur_sup.fetchall()]
print(f"\nSample Case.OrderItemId__c values: {case_oi_ids}")

# Check overlap
overlap = set(oi_ids_clean) & set(r.strip().lstrip('#') if r else '' for r in case_oi_ids)
print(f"Overlap between OrderItems and Case OrderItemId__c: {overlap}")

# Try via OrderId linkage (Case -> OrderItem -> Order -> OrderItem.Product2Id path)
print("\n=== Alternative path: Order relationship ===")
cur_po.execute("PRAGMA table_info('Order')")
order_cols = [c[1] for c in cur_po.fetchall()]
print("Order columns:", order_cols)
cur_po.execute("PRAGMA table_info('OrderItem')")
oi_full_cols = [c[1] for c in cur_po.fetchall()]
print("OrderItem columns:", oi_full_cols)

conn_po.close()
conn_sup.close()
