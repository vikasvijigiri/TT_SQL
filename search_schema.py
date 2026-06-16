import json
import os

db_file = 'resources/databases/snowflake/IDC/IDC_V17/DICOM_ALL.json'
with open(db_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

search_terms = ['normal', 'tumor']
for column in data.get('columns', []):
    col_name = column.get('column_name')
    sample_values = column.get('sample_values', [])
    for val in sample_values:
        if any(term in str(val).lower() for term in search_terms):
            print(f"Column: {col_name} | Value: {val}")
            break
