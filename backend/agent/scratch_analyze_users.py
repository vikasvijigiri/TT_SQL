import os, glob
from datetime import datetime
import re
from collections import defaultdict

base_dir = r'C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\results\evaluations\users'
files = glob.glob(os.path.join(base_dir, '**', '*.md'), recursive=True)
files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

print('Top 5 newest files across all users:')
for f in files[:5]:
    print(datetime.fromtimestamp(os.path.getmtime(f)), f)

now = datetime.now()
target_files = [f for f in files if (now - datetime.fromtimestamp(os.path.getmtime(f))).total_seconds() < 1800] # last 30 mins
print(f'\nFound {len(target_files)} queries modified recently across all users')

agent_fails = defaultdict(int)
agent_calls = defaultdict(int)
failed_queries = 0

for f in target_files:
    try:
        content = open(f, 'r', encoding='utf-8', errors='replace').read()
        if 'passed": false' in content or 'passed: false' in content.lower() or 'FAIL' in content:
            failed_queries += 1
            
        for match in re.finditer(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ([A-Z_]+) - (INFO|WARNING|ERROR) - (.*)', content):
            agent = match.group(1).strip()
            level = match.group(2).strip()
            if agent in ['ROOT', 'MAIN', 'DAB_EVALUATOR', 'AGENT', 'RESULT']: continue
            agent_calls[agent] += 1
            if level in ['ERROR', 'WARNING']:
                agent_fails[agent] += 1
    except Exception as e:
        print("Error reading", f, e)

print(f'\nTotal queries in this batch: {len(target_files)}')
print(f'Total failed queries: {failed_queries}')
print('\nAgent Failures / Calls:')
for agent in sorted(agent_calls.keys(), key=lambda x: agent_fails[x], reverse=True):
    pct = agent_fails[agent]/agent_calls[agent]*100 if agent_calls[agent] > 0 else 0
    print(f'  {agent}: {agent_fails[agent]} errors / {agent_calls[agent]} calls ({pct:.1f}%)')

print('\nTop 10 Most Common Errors:')
import collections
error_messages = collections.Counter()
for f in target_files:
    try:
        content = open(f, 'r', encoding='utf-8', errors='replace').read()
        for match in re.finditer(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ([A-Z_]+) - (INFO|WARNING|ERROR) - (.*)', content):
            level = match.group(2).strip()
            if level in ['ERROR', 'WARNING']:
                msg = match.group(3).strip()
                if 'Pydantic Validation Failed' in msg:
                    error_messages['Pydantic Validation Failed'] += 1
                elif 'DuckDB Execution Error' in msg:
                    error_messages['DuckDB Execution Error'] += 1
                elif 'Catalog Error' in msg:
                    error_messages['Catalog Error'] += 1
                else:
                    error_messages[msg[:100]] += 1
    except: pass

for msg, count in error_messages.most_common(10):
    print(f'  {count}x: {msg}')

