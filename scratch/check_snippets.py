import json
from pathlib import Path

for ds, qid in [('crmarenapro','1'),('stockmarket','1'),('yelp','1'),('stockmarket','3')]:
    ef = Path('backend/results/dab') / ds / f'query{qid}_eval.json'
    if ef.exists():
        d = json.load(open(ef))
        print(f"=== {ds}/q{qid} passed={d['passed']} method={d['method']}")
        print(repr(d.get('agent_answer_snippet','')[:400]))
        print()
