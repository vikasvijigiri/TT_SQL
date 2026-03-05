import os
import csv
from pathlib import Path

def get_success_ids():
    project_root = Path(r"c:\Users\VikasVijigiri\Documents\TT_SQL")
    model_dir = project_root / "results" / "bedrock_openai.gpt-oss-safeguard-120b"
    csv_dir = model_dir / "csv"
    failed_ids_path = project_root / "failed_ids.csv"
    success_ids_path = project_root / "success_ids.csv"

    # Get all produced CSV IDs
    csv_ids = set()
    if csv_dir.exists():
        for f in csv_dir.glob("*.csv"):
            csv_ids.add(f.stem)

    # Get failed IDs
    failed_ids = set()
    if failed_ids_path.exists():
        with open(failed_ids_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                id_val = row.get('instance_id')
                if id_val:
                    failed_ids.add(id_val)

    # Success = Produced CSV AND NOT in failed list
    success_ids = sorted(list(csv_ids - failed_ids))

    with open(success_ids_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['instance_id'])
        for iid in success_ids:
            writer.writerow([iid])

    print(f"Found {len(success_ids)} success IDs. Saved to {success_ids_path}")

if __name__ == "__main__":
    get_success_ids()
