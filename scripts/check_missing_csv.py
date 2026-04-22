import os
from pathlib import Path

def find_missing_results(results_base):
    missing_instances = []
    
    # Walk through the results directory
    for root, dirs, files in os.walk(results_base):
        # Look for 'logs' folders
        if os.path.basename(root) == 'logs':
            csv_folder = os.path.join(os.path.dirname(root), 'csv')
            
            for file in files:
                if file.endswith('.log'):
                    instance_id = os.path.splitext(file)[0]
                    csv_file = instance_id + '.csv'
                    csv_path = os.path.join(csv_folder, csv_file)
                    
                    if not os.path.exists(csv_path):
                        missing_instances.append({
                            'instance_id': instance_id,
                            'log_path': os.path.join(root, file),
                            'csv_path': csv_path
                        })
                        
    # For Version 2 structure (if any) - folder 'log' and extension '.md'
    for root, dirs, files in os.walk(results_base):
        if os.path.basename(root) == 'log':
            csv_folder = os.path.join(os.path.dirname(root), 'csv')
            
            for file in files:
                if file.endswith('.md'):
                    instance_id = os.path.splitext(file)[0]
                    csv_file = instance_id + '.csv'
                    csv_path = os.path.join(csv_folder, csv_file)
                    
                    if not os.path.exists(csv_path):
                        missing_instances.append({
                            'instance_id': instance_id,
                            'log_path': os.path.join(root, file),
                            'csv_path': csv_path
                        })
                        
    return missing_instances

if __name__ == "__main__":
    results_dir = "results"
    missing = find_missing_results(results_dir)
    
    if not missing:
        print("No missing CSV results found.")
    else:
        print(f"Found {len(missing)} instances with logs but missing CSVs:")
        print("-" * 50)
        # Use a set to avoid duplicates if multiple structures overlap
        unique_ids = sorted(list(set(m['instance_id'] for m in missing)))
        for iid in unique_ids:
            print(f"- {iid}")
        
        print("\nDetails:")
        for m in missing:
            print(f"ID: {m['instance_id']}")
            print(f"  Log: {m['log_path']}")
            print(f"  Missing CSV: {m['csv_path']}")
