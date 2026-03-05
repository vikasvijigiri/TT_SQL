import os
import argparse
from pathlib import Path

def consolidate_reports(analysis_dir: Path, output_file: Path, title: str):
    """
    Consolidates all markdown reports in analysis_dir into a single output_file.
    """
    if not analysis_dir.exists():
        print(f"Error: Directory {analysis_dir} does not exist.")
        return

    # Get all .md files and sort them
    report_files = sorted([f for f in analysis_dir.glob("*.md") if f.name != output_file.name])
    
    if not report_files:
        print(f"No reports found in {analysis_dir}")
        return

    print(f"Consolidating {len(report_files)} reports from {analysis_dir} into {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write(f"# {title}\n\n")
        
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
    parser = argparse.ArgumentParser(description="Consolidate reports into a single file.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--type", choices=['success', 'failure'], required=True)
    args = parser.parse_args()

    safe_name = args.model.replace("/", "_").replace(":", "_")
    project_root = Path(__file__).resolve().parent.parent
    
    if args.type == 'success':
        analysis_dir = project_root / "results" / safe_name / "success_reasons"
        output_file = project_root / "results" / safe_name / "summary_success_analysis.md"
        title = "Consolidated Success Analysis Reports"
    else:
        analysis_dir = project_root / "results" / safe_name / "failed_reasons"
        output_file = project_root / "results" / safe_name / "summary_failure_analysis.md"
        title = "Consolidated Failure Analysis Reports"

    consolidate_reports(analysis_dir, output_file, title)

if __name__ == "__main__":
    main()
