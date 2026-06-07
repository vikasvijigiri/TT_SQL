import json, os, glob

datasets = ["agnews","DEPS_DEV_V1","PANCANCER_ATLAS","PATENTS","stockindex","yelp"]
base = "backend/results/dab"

for ds in datasets:
    path = os.path.join(base, ds)
    files = sorted(glob.glob(f"{path}/query*_eval.json"))
    print(f"\n=== {ds} ({len(files)} evals) ===")
    for f in files:
        try:
            with open(f) as fp:
                d = json.load(fp)
            passed = d.get("passed", False)
            reason = str(d.get("failure_reason", d.get("reason", "")))[:140]
            sql_ok = d.get("execution_success", d.get("sql_executed", "?"))
            gen_sql = str(d.get("generated_sql", ""))[:80]
            print(f"  {os.path.basename(f)}: passed={passed} | sql_ok={sql_ok} | {reason}")
            if not passed and gen_sql:
                print(f"    SQL: {gen_sql}")
        except Exception as e:
            print(f"  {os.path.basename(f)}: ERROR - {e}")
