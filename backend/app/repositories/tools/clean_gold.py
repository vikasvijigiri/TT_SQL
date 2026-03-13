import csv
import glob
import os

GOLD_DIR = r"C:\Users\VikasVijigiri\Documents\TT_SQL\gold\exec_result"

def clean_gold_csvs():
    csv_files = glob.glob(os.path.join(GOLD_DIR, "*.csv"))
    print(f"Found {len(csv_files)} CSV files in {GOLD_DIR}")
    
    cleaned_count = 0
    
    junk_keywords = {
        'intent:', 'entities (tables involved):', 'metrics (what to calculate):', 
        'joins:', 'sorting:', 'limits:', 'output format:', 'assumptions:', 'refined_assumptions:',
        'time constraints:', 'dimensions (grouping columns):', 'filters:'
    }
    
    for file_path in csv_files:
        try:
            with open(file_path, "r", newline='', encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            if not rows:
                continue
                
            headers = rows[0]
            # Identify indices to drop
            indices_to_drop = set()
            
            # Check headers
            for i, h in enumerate(headers):
                h_lower = h.strip().lower()
                if any(k in h_lower for k in junk_keywords):
                    indices_to_drop.add(i)
            
            # Check first few rows for junk in "Unnamed" columns
            # (csv module doesn't name them "Unnamed", they are just empty strings usually if missing header)
            # But here the file likely has headers like "Intent:" which we caught above.
            # If the header is empty string "", check the content.
            
            for i, h in enumerate(headers):
                if i in indices_to_drop: continue
                
                # Check column content in first 5 rows
                is_junk_col = False
                for row in rows[1:6]:
                    if i < len(row):
                        val = row[i].strip().lower()
                        if any(k in val for k in junk_keywords):
                            is_junk_col = True
                            break
                if is_junk_col:
                    indices_to_drop.add(i)
            
            if indices_to_drop:
                # print(f"Cleaning {os.path.basename(file_path)}: Dropping indices {indices_to_drop}")
                
                new_rows = []
                for row in rows:
                    new_row = [x for i, x in enumerate(row) if i not in indices_to_drop]
                    # Also remove empty columns at end if they were just commas
                    # We can strip trailing empty strings?
                    # Be careful not to strip valid empty data.
                    # Just keep non-junk indices for now.
                    new_rows.append(new_row)
                    
                # Write back
                with open(file_path, "w", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(new_rows)
                    
                cleaned_count += 1
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print(f"Finished. Cleaned {cleaned_count} files.")

if __name__ == "__main__":
    clean_gold_csvs()
