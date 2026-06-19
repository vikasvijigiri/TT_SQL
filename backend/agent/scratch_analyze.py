import os
import glob
from datetime import datetime
import re
from collections import defaultdict

base_dir = r'C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\results\evaluations\users\default_user\dab'
md_files = glob.glob(os.path.join(base_dir, '**', '*.md'), recursive=True)

target_files = []
now = datetime.now()
print(f'Current time: {now}')

for f in md_files:
    mtime = datetime.fromtimestamp(os.path.getmtime(f))
    # If modified within the last 15 minutes (since user said 4:28 PM and it's 4:29 PM)
    if (now - mtime).total_seconds() < 900:
        target_files.append((f, mtime))

print(f'Found {len(target_files)} queries modified in the last 15 mins')

agent_fails = defaultdict(int)
agent_calls = defaultdict(int)
total_queries = len(target_files)
failed_queries = 0

for f, _ in target_files:
    try:
        content = open(f, 'r', encoding='utf-8', errors='replace').read()
        if 'passed": false' in content or 'passed: false' in content.lower():
            failed_queries += 1
        elif 'Evaluation Result:' in content and 'FAIL' in content:
            failed_queries += 1
            
        for match in re.finditer(r'\|\s*([A-Z_]+)\s*\|\s*(INFO|WARNING|ERROR)\s*\|(.*)', content):
            agent = match.group(1).strip()
            level = match.group(2).strip()
            msg = match.group(3).strip()
            if agent in ['ROOT', 'MAIN', 'DAB_EVALUATOR', 'AGENT']: continue
            agent_calls[agent] += 1
            if level in ['ERROR', 'WARNING']:
                agent_fails[agent] += 1
    except Exception as e:
        print("Error parsing", f, e)

print(f'\nTotal queries in this batch: {total_queries}')
print(f'Total failed queries: {failed_queries}')
print('\nAgent Failures / Calls:')
for agent in sorted(agent_calls.keys(), key=lambda x: agent_fails[x], reverse=True):
    pct = agent_fails[agent]/agent_calls[agent]*100 if agent_calls[agent] > 0 else 0
    print(f'  {agent}: {agent_fails[agent]} errors / {agent_calls[agent]} calls ({pct:.1f}%)')
