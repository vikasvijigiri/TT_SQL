import os
import argparse
from pathlib import Path

def consolidate_reports(analysis_dir: Path, output_file: Path):
    """
    Consolidates all markdown reports in analysis_dir into a single output_file.
    """
    if not analysis_dir.exists():
        print(f"Error: Directory {analysis_dir} does not exist.")
        return

    # Get all .md files and sort them (e.g., local001.md, local002.md)
    report_files = sorted([f for f in analysis_dir.glob("*.md") if f.name != output_file.name])
    
    if not report_files:
        print(f"No reports found in {analysis_dir}")
        return

    print(f"Consolidating {len(report_files)} reports from {analysis_dir} into {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write("# Consolidated Failure Analysis Reports\n\n")
        
        for fpath in report_files:
            instance_id = fpath.stem
            
            # Read content
            with open(fpath, 'r', encoding='utf-8') as infile:
                content = infile.read().strip()
            
            # Write separator and content
            outfile.write("______________________\n")
            outfile.write(f"Ex: {instance_id}\n")
            outfile.write("______________________\n\n")
            outfile.write(content)
            outfile.write("\n\n")

    print(f"Successfully consolidated reports to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Consolidate failure analysis reports into a single file.")
    parser.add_argument("--model", required=True, help="Model name (used for directory mapping)")
    args = parser.parse_args()

    # Mapping logic (mirroring the main pipeline)
    safe_name = args.model.replace("/", "_").replace(":", "_")
    project_root = Path(__file__).resolve().parent.parent
    analysis_dir = project_root / "results" / safe_name / "failed_reasons"
    output_file = project_root / "results" / safe_name / "summary_failure_analysis.md"

    consolidate_reports(analysis_dir, output_file)

if __name__ == "__main__":
    main()
