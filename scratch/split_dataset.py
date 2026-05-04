import json
import os

def split_jsonl(input_file, output_dir):
    snowflake_tasks = []
    bigquery_tasks = []
    sqlite_tasks = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            task = json.loads(line)
            instance_id = task.get("instance_id", "")
            
            if instance_id.startswith("sf_bq") or instance_id.startswith("sf"):
                snowflake_tasks.append(task)
            elif instance_id.startswith("bq"):
                bigquery_tasks.append(task)
            elif instance_id.startswith("local"):
                sqlite_tasks.append(task)
            else:
                # Default to sqlite if pattern doesn't match?
                sqlite_tasks.append(task)
                
    # Write files
    def write_tasks(tasks, filename):
        path = os.path.join(output_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            for t in tasks:
                f.write(json.dumps(t) + '\n')
        print(f"Wrote {len(tasks)} tasks to {path}")

    write_tasks(snowflake_tasks, "spider2-lite-snowflake.jsonl")
    write_tasks(bigquery_tasks, "spider2-lite-bigquery.jsonl")
    write_tasks(sqlite_tasks, "spider2-lite-sqlite.jsonl")

if __name__ == "__main__":
    input_path = "input_data/spider2-lite.jsonl"
    output_path = "input_data"
    split_jsonl(input_path, output_path)
