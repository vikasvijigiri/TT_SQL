import json
for q in ['1','2','3']:
    with open(f'backend/results/dab/stockindex/query{q}_eval.json') as f:
        d = json.load(f)
    passed = d['passed']
    reason = d['reason']
    snippet = d.get('agent_answer_snippet','')[:150]
    print(f"Q{q}: passed={passed}")
    print(f"     reason:  {reason}")
    print(f"     snippet: {snippet!r}")
    print()
