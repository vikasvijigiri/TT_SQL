import pandas as pd
import pathlib

dab_repo = pathlib.Path(r"C:\Users\VikasVijigiri\Documents\DataAgentBench")
targets = [
    ("query_GITHUB_REPOS", "query1"),
    ("query_GITHUB_REPOS", "query2"),
    ("query_GITHUB_REPOS", "query3"),
    ("query_music_brainz_20k", "query1"),
    ("query_stockindex", "query3")
]

for ds, q in targets:
    gt_path = dab_repo / ds / q / "ground_truth.csv"
    if gt_path.exists():
        print(f"\n==========================================")
        print(f"Ground Truth for {ds} {q}")
        print(f"==========================================")
        df = pd.read_csv(gt_path)
        print(df.to_string())
