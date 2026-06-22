import re

with open(r"C:\Users\VIKASV~1\AppData\Local\Temp\claude\c--Users-VikasVijigiri-Documents-TT-SQL-V2\55932db9-6e92-418d-843a-631a2fbb41c8\tasks\bspu1p5v1.output", encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find stockmarket section
stk_start = content.find('DAB: STOCKMARKET / QUERY 4')
stk_end = content.find('stockmarket/q4] DONE')
if stk_start > 0 and stk_end > 0:
    section = content[stk_start:stk_end]
    # Find all SQL blocks
    sql_matches = re.findall(r'"sql":\s*"((?:[^"\\]|\\.)+)"', section)
    for i, sql in enumerate(sql_matches[:5]):
        print(f"\n=== SQL Attempt {i+1} ===")
        print(sql.replace('\\n', '\n').replace('\\"', '"')[:800])

    # Find stockinfo attachment logs
    attach_lines = [l for l in section.split('\n') if 'stockinfo' in l.lower() or 'attach' in l.lower() or 'AGENT ANSWER' in l or 'No results' in l or 'Company' in l or 'auto-attach' in l.lower()]
    print("\n=== Stockinfo/Attach logs ===")
    for line in attach_lines[:20]:
        print(line[:250])
else:
    print("Stockmarket section not found. Start:", stk_start, "End:", stk_end)
    print("Searching for key terms...")
    for term in ['MFA Financial', 'Company Description', 'stockinfo_query', 'auto-attach']:
        idx = content.find(term)
        if idx > 0:
            print(f"Found '{term}' at {idx}: ...{content[idx-50:idx+100]}...")
