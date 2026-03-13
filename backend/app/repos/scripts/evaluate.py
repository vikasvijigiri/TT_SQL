import argparse
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from threading import Lock

import pandas as pd
from google.cloud import bigquery
from tqdm import tqdm


class TeeOutput:
    """Mirror stdout/stderr to both console and a logfile with thread safety."""

    def __init__(self, filename: str):
        self.console = sys.stdout
        self.file = open(filename, "w")
        self.lock = Lock()

    def write(self, message: str) -> None:
        with self.lock:
            self.console.write(message)
            self.file.write(message)

    def flush(self) -> None:
        with self.lock:
            self.console.flush()
            self.file.flush()

    def close(self) -> None:
        self.file.close()


sys.stdout = TeeOutput("log.txt")
sys.stderr = sys.stdout


TOTAL_GB_PROCESSED = 0.0
GB_LOCK = Lock()


@lru_cache(maxsize=None)
def load_gold_csv(file_path: str) -> pd.DataFrame:
    """Cache gold CSV loads to avoid repeated disk reads during evaluation."""
    return pd.read_csv(file_path)


def load_jsonl_to_dict(jsonl_file: str) -> dict:
    data_dict = {}
    with open(jsonl_file, "r") as file:
        for line in file:
            item = json.loads(line.strip())
            instance_id = item["instance_id"]
            data_dict[instance_id] = item
    return data_dict


def compare_multi_pandas_table(pred: pd.DataFrame, multi_gold, multi_condition_cols=None, multi_ignore_order=False) -> int:
    if not multi_gold:
        return 0

    if multi_condition_cols in (None, [], [[]], [None]):
        multi_condition_cols = [[] for _ in range(len(multi_gold))]
    elif len(multi_gold) > 1 and not all(isinstance(sublist, list) for sublist in multi_condition_cols):
        multi_condition_cols = [multi_condition_cols for _ in range(len(multi_gold))]

    multi_ignore_order = [multi_ignore_order for _ in range(len(multi_gold))]

    for i, gold in enumerate(multi_gold):
        if compare_pandas_table(pred, gold, multi_condition_cols[i], multi_ignore_order[i]):
            return 1
    return 0


def compare_pandas_table(pred: pd.DataFrame, gold: pd.DataFrame, condition_cols=None, ignore_order: bool = False) -> int:
    tolerance = 1e-2

    def normalize(value):
        if pd.isna(value):
            return 0
        return value

    def vectors_match(v1, v2, tol=tolerance, ignore_order_=False):
        v1 = [normalize(x) for x in v1]
        v2 = [normalize(x) for x in v2]

        if ignore_order_:
            v1 = sorted(v1, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))
            v2 = sorted(v2, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))

        if len(v1) != len(v2):
            return False

        for a, b in zip(v1, v2):
            if pd.isna(a) and pd.isna(b):
                continue
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(float(a), float(b), abs_tol=tol):
                    return False
            elif a != b:
                return False
        return True

    if condition_cols:
        if not isinstance(condition_cols, (list, tuple)):
            condition_cols = [condition_cols]
        gold_cols = gold.iloc[:, condition_cols]
    else:
        gold_cols = gold

    pred_cols = pred
    t_gold_list = gold_cols.transpose().values.tolist()
    t_pred_list = pred_cols.transpose().values.tolist()
    score = 1

    for gold_vector in t_gold_list:
        if not any(vectors_match(gold_vector, pred_vector, ignore_order_=ignore_order) for pred_vector in t_pred_list):
            score = 0
            break

    return score


def get_bigquery_sql_result(sql_query: str, is_save: bool, save_dir=None, file_name: str = "result.csv", instance_id: str = None):
    global TOTAL_GB_PROCESSED

    prefix = f"[{instance_id}] " if instance_id else ""
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "bigquery_credential.json")

    try:
        client = bigquery.Client()
        query_job = client.query(sql_query)
        results = query_job.result().to_dataframe()
        total_bytes_processed = query_job.total_bytes_processed or 0
        gb_processed = total_bytes_processed / (1024 ** 3)

        with GB_LOCK:
            TOTAL_GB_PROCESSED += gb_processed
            total_gb = TOTAL_GB_PROCESSED

        print(f"{prefix}GB processed: {gb_processed:.5f} GB")
        print(f"{prefix}Total GB processed: {total_gb:.5f} GB")

        if results.empty:
            message = "No data found for the specified query."
            print(f"{prefix}{message}")
            if is_save and save_dir:
                os.makedirs(save_dir, exist_ok=True)
                results.to_csv(os.path.join(save_dir, file_name), index=False)
            return False, message

        if is_save and save_dir:
            os.makedirs(save_dir, exist_ok=True)
            results.to_csv(os.path.join(save_dir, file_name), index=False)

        return True, None
    except Exception as e:
        error_message = str(e)
        print(f"{prefix}Error occurred while fetching data: {error_message}")
        return False, error_message


def get_sqlite_result(db_path: str, query: str, save_dir=None, file_name: str = "result.csv", chunksize: int = 500, instance_id: str = None):
    prefix = f"[{instance_id}] " if instance_id else ""

    try:
        conn = sqlite3.connect(db_path)
        memory_conn = sqlite3.connect(":memory:")
        conn.backup(memory_conn)

        try:
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
                for i, chunk in enumerate(pd.read_sql_query(query, memory_conn, chunksize=chunksize)):
                    mode = "a" if i > 0 else "w"
                    header = i == 0
                    chunk.to_csv(os.path.join(save_dir, file_name), mode=mode, header=header, index=False)
                return True, None

            df = pd.read_sql_query(query, memory_conn)
            return True, df
        finally:
            memory_conn.close()
            conn.close()
    except Exception as e:
        error_message = str(e)
        print(f"{prefix}An error occurred: {error_message}")
        return False, error_message


def extract_sql_query(pred_sql_query: str) -> str:
    pattern = r"```sql\n(.*?)\n```"
    match = re.search(pattern, pred_sql_query, re.DOTALL)

    if match:
        return match.group(1).strip()
    return pred_sql_query


def resolve_gold_paths(instance_id: str, gold_result_dir: str):
    base_path = Path(gold_result_dir) / f"{instance_id}.csv"
    if base_path.exists():
        return [base_path], True

    if "_" in instance_id:
        pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")
    else:
        pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")

    csv_files = sorted(
        file for file in os.listdir(gold_result_dir)
        if pattern.match(file)
    )
    return [Path(gold_result_dir) / file for file in csv_files], False


def evaluate_single_sql_instance(
    instance_id: str,
    eval_standard_dict: dict,
    spider2sql_metadata: dict,
    pred_result_dir: str,
    gold_result_dir: str,
    temp_dir: Path,
    result_csv_dir: str = None,
    timeout: int = 60,
    sqlite_base_dir: Path = None,
):
    del timeout  # timeout currently unused for lite databases

    error_info = None
    score = 0
    pred_sql_query = ""

    try:
        pred_sql_path = Path(pred_result_dir) / f"{instance_id}.sql"
        pred_sql_query = pred_sql_path.read_text()
        pred_sql_query = extract_sql_query(pred_sql_query)

        thread_temp_dir = Path(temp_dir) / f"thread_{threading.get_ident()}_{instance_id}"
        thread_temp_dir.mkdir(parents=True, exist_ok=True)
        result_file = f"{instance_id}.csv"

        if instance_id.startswith(("bq", "ga")):
            exe_flag, dbms_error_info = get_bigquery_sql_result(
                pred_sql_query,
                True,
                save_dir=str(thread_temp_dir),
                file_name=result_file,
                instance_id=instance_id,
            )
        elif instance_id.startswith("local"):
            metadata = spider2sql_metadata.get(instance_id, {})
            db_name = metadata.get("db")
            if not db_name:
                exe_flag = False
                dbms_error_info = f"Missing database mapping for {instance_id}"
            else:
                sqlite_path = sqlite_base_dir / f"{db_name}.sqlite"
                exe_flag, dbms_error_info = get_sqlite_result(
                    str(sqlite_path),
                    pred_sql_query,
                    save_dir=str(thread_temp_dir),
                    file_name=result_file,
                    instance_id=instance_id,
                )
        else:
            exe_flag = False
            dbms_error_info = f"Unsupported instance id prefix: {instance_id}"

        if not exe_flag:
            score = 0
            error_info = dbms_error_info
        else:
            pred_csv_path = thread_temp_dir / result_file
            pred_pd = pd.read_csv(pred_csv_path)

            if result_csv_dir:
                os.makedirs(result_csv_dir, exist_ok=True)
                shutil.copy2(pred_csv_path, Path(result_csv_dir) / result_file)

            gold_paths, is_single = resolve_gold_paths(instance_id, gold_result_dir)
            standard = eval_standard_dict.get(instance_id, {})
            condition_cols = standard.get("condition_cols")
            ignore_order = standard.get("ignore_order", False)

            if not gold_paths:
                score = 0
                error_info = error_info or "No matching gold file found"
            elif is_single:
                try:
                    gold_pd = load_gold_csv(str(gold_paths[0]))
                    score = compare_pandas_table(pred_pd, gold_pd, condition_cols, ignore_order)
                except Exception as e:
                    print(f"{instance_id}: compare against {gold_paths[0]} failed: {e}")
                    score = 0
                    error_info = f"Python Script Error:{str(e)}"
                if score == 0 and error_info is None:
                    error_info = "Result Error"
            else:
                try:
                    gold_pds = [load_gold_csv(str(path)) for path in gold_paths]
                    score = compare_multi_pandas_table(pred_pd, gold_pds, condition_cols, ignore_order)
                except Exception as e:
                    print(f"{instance_id}: multi-compare against {gold_paths} failed: {e}")
                    score = 0
                    error_info = f"Python Script Error:{str(e)}"
                if score == 0 and error_info is None:
                    error_info = "Result Error"

    except Exception as e:
        print(f"Error evaluating {instance_id}: {e}")
        score = 0
        error_info = f"Evaluation Error: {str(e)}"
        pred_sql_query = ""

    return {
        "instance_id": instance_id,
        "score": score,
        "pred_sql": pred_sql_query,
        "error_info": error_info,
    }


def evaluate_single_exec_result_instance(
    instance_id: str,
    eval_standard_dict: dict,
    pred_result_dir: str,
    gold_result_dir: str,
):
    error_info = None

    try:
        pred_pd = pd.read_csv(Path(pred_result_dir) / f"{instance_id}.csv")

        gold_paths, is_single = resolve_gold_paths(instance_id, gold_result_dir)
        standard = eval_standard_dict.get(instance_id, {})
        condition_cols = standard.get("condition_cols")
        ignore_order = standard.get("ignore_order", False)

        if not gold_paths:
            score = 0
            error_info = "No matching gold file found"
        elif is_single:
            try:
                gold_pd = load_gold_csv(str(gold_paths[0]))
                score = compare_pandas_table(pred_pd, gold_pd, condition_cols, ignore_order)
            except Exception as e:
                print(f"{instance_id}: compare against {gold_paths[0]} failed: {e}")
                score = 0
                error_info = f"Python Script Error:{str(e)}"
            if score == 0 and error_info is None:
                error_info = "Result Error"
        else:
            try:
                gold_pds = [load_gold_csv(str(path)) for path in gold_paths]
                score = compare_multi_pandas_table(pred_pd, gold_pds, condition_cols, ignore_order)
            except Exception as e:
                print(f"{instance_id}: multi-compare against {gold_paths} failed: {e}")
                score = 0
                error_info = f"Python Script Error:{str(e)}"
            if score == 0 and error_info is None:
                error_info = "Result Error"

    except Exception as e:
        print(f"{instance_id} ERROR!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! {e}")
        score = 0
        error_info = f"Evaluation Error: {str(e)}"

    return {
        "instance_id": instance_id,
        "score": score,
        "pred_sql": None,
        "error_info": error_info,
    }


def save_correct_ids_to_csv(output_results, result_dir: str):
    correct_ids = [item["instance_id"] for item in output_results if item["score"] == 1]

    transformed_ids = []
    for item in correct_ids:
        if item.startswith(("bq", "ga", "local")):
            transformed_ids.append(f"sf_{item}")
        else:
            transformed_ids.append(item)

    csv_file = f"{result_dir}-ids.csv"
    pd.DataFrame({"instance_id": transformed_ids}).to_csv(csv_file, index=False)
    print(f"Correct IDs saved to: {csv_file}")
    return csv_file


def evaluate_generalized(args, temp_dir: Path):
    mode = args.mode
    # Generalize: allow override for the subfolder inside gold_dir
    # Default gold structure: gold/spider2_gold/exec_result
    gold_exec_dir = args.gold_exec_dir if args.gold_exec_dir else os.path.join(args.gold_dir, "spider2_gold", "exec_result")
    pred_result_dir = args.result_dir

    # Generalize: allow override for eval jsonl
    # Check if spider2_gold is inside the centralized gold_dir
    central_jsonl = os.path.join(args.gold_dir, "spider2_gold", "spider2lite_eval.jsonl")
    eval_jsonl_path = args.eval_jsonl if args.eval_jsonl else (central_jsonl if os.path.exists(central_jsonl) else os.path.join(PACKAGE_ROOT, "gold", "spider2_gold", "spider2lite_eval.jsonl"))
    if not os.path.exists(eval_jsonl_path):
        print(f"⚠️ Warning: Evaluation standard file not found at {eval_jsonl_path}")
        eval_standard_dict = {}
    else:
        eval_standard_dict = load_jsonl_to_dict(eval_jsonl_path)

    # Generalize: allow override for metadata
    PACKAGE_ROOT = Path(__file__).resolve().parent.parent
    meta_jsonl_path = args.meta_jsonl if args.meta_jsonl else str(PACKAGE_ROOT / "input_queries" / "spider2-lite.jsonl")
    if not os.path.exists(meta_jsonl_path):
        print(f"⚠️ Warning: Metadata file not found at {meta_jsonl_path}")
        metadata_dict = {}
    else:
        metadata_dict = load_jsonl_to_dict(meta_jsonl_path)

    # Generalize: allow override for DB dir
    db_base_dir = Path(args.db_dir) if args.db_dir else project_root / "resources" / "spider2-localdb"

    result_csv_dir = None
    if mode == "sql":
        result_csv_path = Path(f"{pred_result_dir}_csv")
        if result_csv_path.exists():
            shutil.rmtree(result_csv_path)
        result_csv_path.mkdir(parents=True, exist_ok=True)
        result_csv_dir = str(result_csv_path)

    pred_ids = []
    if mode == "sql":
        if os.path.exists(pred_result_dir):
            pred_ids = [Path(file).stem for file in os.listdir(pred_result_dir) if file.endswith(".sql")]
    elif mode == "exec_result":
        if os.path.exists(pred_result_dir):
            pred_ids = [Path(file).stem for file in os.listdir(pred_result_dir) if file.endswith(".csv")]

    gold_ids = list(eval_standard_dict.keys()) if eval_standard_dict else pred_ids
    eval_ids = sorted(set(gold_ids).intersection(pred_ids)) if eval_standard_dict else pred_ids

    if not eval_ids:
        print("❌ No matching prediction IDs found to evaluate.")
        return []

    max_workers = getattr(args, "max_workers", 8)
    max_workers = min(max_workers, len(eval_ids)) or 1

    output_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if mode == "sql":
            future_to_id = {
                executor.submit(
                    evaluate_single_sql_instance_generalized,
                    instance_id,
                    eval_standard_dict,
                    metadata_dict,
                    pred_result_dir,
                    gold_exec_dir,
                    temp_dir=temp_dir,
                    result_csv_dir=result_csv_dir,
                    db_base_dir=db_base_dir,
                ): instance_id
                for instance_id in eval_ids
            }
        else:
            future_to_id = {
                executor.submit(
                    evaluate_single_exec_result_instance,
                    instance_id,
                    eval_standard_dict,
                    pred_result_dir,
                    gold_exec_dir,
                ): instance_id
                for instance_id in eval_ids
            }

        desc = "Evaluating SQL" if mode == "sql" else "Evaluating Exec Results"
        for future in tqdm(as_completed(future_to_id), total=len(eval_ids), desc=desc):
            output_results.append(future.result())

    output_results.sort(key=lambda item: item["instance_id"])

    # Metrics
    correct_count = sum(item["score"] for item in output_results)
    total_evaluated = len(output_results)
    accuracy = (correct_count / total_evaluated) if total_evaluated > 0 else 0

    print(f"\n--- EVALUATION SUMMARY ---")
    print(f"Total Evaluated: {total_evaluated}")
    print(f"Correct: {correct_count}")
    print(f"Accuracy: {accuracy:.4f}")
    
    if args.meta_jsonl and "spider2-lite" not in args.meta_jsonl:
        # For non-spider cases, we don't need the 547 baseline
        pass
    else:
        # Keep Spider2 baseline for backward compatibility if it looks like spider
        print(f"Spider2-Lite Baseline Accuracy (Correct / 547): {correct_count / 547:.4f}")

    save_correct_ids_to_csv(output_results, pred_result_dir)
    return output_results

def evaluate_single_sql_instance_generalized(
    instance_id: str,
    eval_standard_dict: dict,
    metadata_dict: dict,
    pred_result_dir: str,
    gold_result_dir: str,
    temp_dir: Path,
    result_csv_dir: str = None,
    db_base_dir: Path = None,
):
    error_info = None
    score = 0
    pred_sql_query = ""

    try:
        pred_sql_path = Path(pred_result_dir) / f"{instance_id}.sql"
        if not pred_sql_path.exists():
            return {"instance_id": instance_id, "score": 0, "pred_sql": "", "error_info": "SQL file missing"}
            
        pred_sql_query = pred_sql_path.read_text(encoding="utf-8")
        pred_sql_query = extract_sql_query(pred_sql_query)

        thread_temp_dir = Path(temp_dir) / f"thread_{threading.get_ident()}_{instance_id}"
        thread_temp_dir.mkdir(parents=True, exist_ok=True)
        result_file = f"{instance_id}.csv"

        # Routing Logic: If instance_id doesn't match BigQuery/GA patterns, assume SQLite
        is_bigquery = instance_id.startswith(("bq", "ga"))
        
        if is_bigquery:
            exe_flag, dbms_error_info = get_bigquery_sql_result(
                pred_sql_query,
                True,
                save_dir=str(thread_temp_dir),
                file_name=result_file,
                instance_id=instance_id,
            )
        else:
            # Check metadata for DB mapping
            metadata = metadata_dict.get(instance_id, {})
            db_name = metadata.get("db") or instance_id.split("_")[1] if "_" in instance_id else None
            
            if not db_name:
                # Fallback: check if a .sqlite file exists with the instance name
                if (db_base_dir / f"{instance_id}.sqlite").exists():
                    db_name = instance_id
            
            if not db_name:
                exe_flag = False
                dbms_error_info = f"Missing database mapping for {instance_id}. (Checked metadata and db_dir)"
            else:
                sqlite_path = db_base_dir / f"{db_name}.sqlite"
                exe_flag, dbms_error_info = get_sqlite_result(
                    str(sqlite_path),
                    pred_sql_query,
                    save_dir=str(thread_temp_dir),
                    file_name=result_file,
                    instance_id=instance_id,
                )

        if not exe_flag:
            score = 0
            error_info = dbms_error_info
        else:
            pred_csv_path = thread_temp_dir / result_file
            pred_pd = pd.read_csv(pred_csv_path)

            if result_csv_dir:
                os.makedirs(result_csv_dir, exist_ok=True)
                shutil.copy2(pred_csv_path, Path(result_csv_dir) / result_file)

            gold_paths, is_single = resolve_gold_paths(instance_id, gold_result_dir)
            standard = eval_standard_dict.get(instance_id, {})
            condition_cols = standard.get("condition_cols")
            ignore_order = standard.get("ignore_order", False)

            if not gold_paths:
                score = 0
                error_info = "No matching gold file found"
            elif is_single:
                gold_pd = load_gold_csv(str(gold_paths[0]))
                score = compare_pandas_table(pred_pd, gold_pd, condition_cols, ignore_order)
            else:
                gold_pds = [load_gold_csv(str(path)) for path in gold_paths]
                score = compare_multi_pandas_table(pred_pd, gold_pds, condition_cols, ignore_order)

    except Exception as e:
        print(f"Error evaluating {instance_id}: {e}")
        score = 0
        error_info = f"Evaluation Error: {str(e)}"

    return {
        "instance_id": instance_id,
        "score": score,
        "pred_sql": pred_sql_query,
        "error_info": error_info,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="generalized TT-SQL Evaluation")
    parser.add_argument("--mode", type=str, choices=["sql", "exec_result"], default="sql")
    parser.add_argument("--result_dir", type=str, required=True, help="Path to predicted SQL or CSV folder")
    parser.add_argument("--gold_dir", type=str, default="evaluation", help="Directory containing gold SQL and exec files")
    parser.add_argument("--gold_exec_dir", type=str, help="Subfolder in gold_dir containing ground truth CSVs")
    parser.add_argument("--eval_jsonl", type=str, help="Path to the JSONL containing evaluation standards (condition_cols, etc.)")
    parser.add_argument("--meta_jsonl", type=str, help="Path to the dataset metadata JSONL (for mapping instances to DBs)")
    parser.add_argument("--db_dir", type=str, help="Directory containing .sqlite databases")
    parser.add_argument("--max_workers", type=int, default=16)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--temp_dir", type=str, default=None)
    
    args = parser.parse_args()

    # Setup temp path
    auto_temp = False
    if args.temp_dir:
        temp_path = Path(args.temp_dir).expanduser().resolve()
        os.makedirs(temp_path, exist_ok=True)
    else:
        temp_path = Path(tempfile.mkdtemp(prefix="tt_eval_"))
        auto_temp = True

    try:
        evaluate_generalized(args, temp_path)
    finally:
        if auto_temp:
            shutil.rmtree(temp_path, ignore_errors=True)
