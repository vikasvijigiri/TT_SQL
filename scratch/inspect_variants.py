import json
import os

path = 'resources/databases/snowflake/IDC/IDC_V17/DICOM_ALL.json'
with open(path) as f:
    d = json.load(f)

var_cols = [c['column_name'] for c in d['columns'] if c['type'] == 'VARIANT']
for c in var_cols:
    keys = set()
    for r in d['sample']:
        val = r.get(c)
        if val is None:
            continue
        # Handle stringified JSON if necessary (though local metadata is usually already objects)
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except:
                continue
        
        if isinstance(val, dict):
            keys.update(val.keys())
        elif isinstance(val, list):
            for i in val:
                if isinstance(i, dict):
                    keys.update(i.keys())
    if keys:
        print(f"{c}: {sorted(list(keys))}")
