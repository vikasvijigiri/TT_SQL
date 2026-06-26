import json
from pathlib import Path
import random

results_file = Path(__file__).resolve().parent.parent.parent.parent / 'dab_submission_bundle/results.json'
metrics = json.loads(results_file.read_text(encoding='utf-8'))

previous = {
    ('crmarenapro', '2'), ('crmarenapro', '5'), ('bookreview', '3'),
    ('patents', '1'), ('music_brainz_20k', '2'), ('stockmarket', '4'),
    ('crmarenapro', '6'), ('yelp', '2'), ('yelp', '4'),
    ('patents', '3'), ('pancancer_atlas', '1'), ('crmarenapro', '7')
}
failed_queries = []

for ds_name, ds_info in metrics['per_dataset'].items():
    for query in ds_info['queries']:
        for run in query['runs']:
            if not run['passed'] and (ds_name, query['query_id']) not in previous:
                failed_queries.append({
                    'dataset': ds_name,
                    'query_id': query['query_id'],
                    'reason': run['reason']
                })
                break

random.shuffle(failed_queries)
for fq in failed_queries[:3]:
    print(f"{fq['dataset']}_{fq['query_id']} - {fq['reason']}")
