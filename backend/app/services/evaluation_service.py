import os
import json
import math
import re
import sqlite3
import shutil
import threading
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from google.cloud import bigquery
from tqdm import tqdm
from typing import List, Dict, Any, Optional, Tuple

from app.services.utils.logger import Logger

class EvaluationService:
    def __init__(self):
        self.total_gb_processed = 0.0
        self.gb_lock = threading.Lock()

    def compare_pandas_table(self, pred: pd.DataFrame, gold: pd.DataFrame, condition_cols=None, ignore_order: bool = False) -> int:
        tolerance = 1e-2
        def normalize(value):
            if pd.isna(value): return 0
            return value

        def vectors_match(v1, v2, tol=tolerance, ignore_order_=False):
            v1 = [normalize(x) for x in v1]
            v2 = [normalize(x) for x in v2]
            if ignore_order_:
                v1 = sorted(v1, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))
                v2 = sorted(v2, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))
            if len(v1) != len(v2): return False
            for a, b in zip(v1, v2):
                if pd.isna(a) and pd.isna(b): continue
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    if not math.isclose(float(a), float(b), abs_tol=tol): return False
                elif a != b: return False
            return True

        if condition_cols is not None:
            try:
                if not isinstance(condition_cols, (list, tuple)):
                    condition_cols = [condition_cols]
                gold_cols = gold.iloc[:, condition_cols]
            except Exception:
                gold_cols = gold
        else:
            gold_cols = gold

        pred_cols = pred
        t_gold_list = gold_cols.transpose().values.tolist()
        t_pred_list = pred_cols.transpose().values.tolist()

        for gold_vector in t_gold_list:
            if not any(vectors_match(gold_vector, pred_vector, ignore_order_=ignore_order) for pred_vector in t_pred_list):
                return 0
        return 1

    def compare_multi_pandas_table(self, pred: pd.DataFrame, multi_gold, multi_condition_cols=None, multi_ignore_order=False) -> int:
        if not multi_gold: return 0
        if multi_condition_cols in (None, [], [[]], [None]):
            multi_condition_cols = [[] for _ in range(len(multi_gold))]
        elif len(multi_gold) > 1 and not all(isinstance(sublist, list) for sublist in multi_condition_cols):
            multi_condition_cols = [multi_condition_cols for _ in range(len(multi_gold))]
        
        for i, gold in enumerate(multi_gold):
            if self.compare_pandas_table(pred, gold, multi_condition_cols[i], multi_ignore_order):
                return 1
        return 0

    def get_bigquery_sql_result(self, sql_query: str, save_dir: str, file_name: str, instance_id: str = None, timeout: int = 90):
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "bigquery_credential.json")
        try:
            client = bigquery.Client()
            
            def execute_query():
                query_job = client.query(sql_query)
                df = query_job.result().to_dataframe()
                self.total_gb_processed += (query_job.total_bytes_processed or 0) / (1024 ** 3)
                return df

            # Simple timeout mechanism using thread wait or signal
            # For simplicity in this environment, we'll keep it direct or use a wrapper if signal is safe on Windows
            results = execute_query() # In production, use a more robust timeout wrapper
            
            if results.empty:
                os.makedirs(save_dir, exist_ok=True)
                results.to_csv(os.path.join(save_dir, file_name), index=False)
                return False, "No data found."
            
            os.makedirs(save_dir, exist_ok=True)
            results.to_csv(os.path.join(save_dir, file_name), index=False)
            return True, None
        except Exception as e:
            return False, str(e)

    def get_snowflake_sql_result(self, sql_query: str, save_dir: str, file_name: str):
        try:
            import snowflake.connector
            snowflake_credential = json.load(open('./credentials/snowflake_credential.json'))
            conn = snowflake.connector.connect(**snowflake_credential)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(results, columns=columns)
            
            os.makedirs(save_dir, exist_ok=True)
            df.to_csv(os.path.join(save_dir, file_name), index=False)
            return True, None
        except Exception as e:
            return False, str(e)

    def extract_sql_query(self, pred_sql_query: str) -> str:
        pattern = r"```sql\n(.*?)\n```"
        match = re.search(pattern, pred_sql_query, re.DOTALL)
        return match.group(1).strip() if match else pred_sql_query

    def resolve_gold_paths(self, instance_id: str, gold_result_dir: str):
        base_path = Path(gold_result_dir) / f"{instance_id}.csv"
        if base_path.exists():
            return [base_path], True

        pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")
        csv_files = sorted(
            file for file in os.listdir(gold_result_dir)
            if pattern.match(file)
        )
        return [Path(gold_result_dir) / file for file in csv_files], False

    def evaluate_single_sql_instance(
        self,
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
                
            pred_sql_query = self.extract_sql_query(pred_sql_path.read_text(encoding="utf-8"))
            thread_temp_dir = Path(temp_dir) / f"thread_{threading.get_ident()}_{instance_id}"
            thread_temp_dir.mkdir(parents=True, exist_ok=True)
            result_file = f"{instance_id}.csv"

            is_bigquery = instance_id.startswith(("bq", "ga"))
            if is_bigquery:
                exe_flag, dbms_err = self.get_bigquery_sql_result(pred_sql_query, str(thread_temp_dir), result_file, instance_id)
            else:
                metadata = metadata_dict.get(instance_id, {})
                db_name = metadata.get("db") or instance_id.split("_")[1] if "_" in instance_id else instance_id
                sqlite_path = db_base_dir / f"{db_name}.sqlite"
                if not sqlite_path.exists():
                    exe_flag, dbms_err = False, f"DB not found: {sqlite_path}"
                else:
                    exe_flag, dbms_err = self.get_sqlite_result(str(sqlite_path), pred_sql_query, str(thread_temp_dir), result_file)

            if not exe_flag:
                score, error_info = 0, dbms_err
            else:
                pred_csv_path = thread_temp_dir / result_file
                pred_pd = pd.read_csv(pred_csv_path)
                if result_csv_dir:
                    os.makedirs(result_csv_dir, exist_ok=True)
                    shutil.copy2(pred_csv_path, Path(result_csv_dir) / result_file)

                gold_paths, is_single = self.resolve_gold_paths(instance_id, gold_result_dir)
                standard = eval_standard_dict.get(instance_id, {})
                cond_cols = standard.get("condition_cols")
                ign_ord = standard.get("ignore_order", False)

                if not gold_paths:
                    score, error_info = 0, "No gold file"
                elif is_single:
                    gold_pd = pd.read_csv(gold_paths[0])
                    score = self.compare_pandas_table(pred_pd, gold_pd, cond_cols, ign_ord)
                else:
                    gold_pds = [pd.read_csv(p) for p in gold_paths]
                    score = self.compare_multi_pandas_table(pred_pd, gold_pds, cond_cols, ign_ord)
        except Exception as e:
            score, error_info = 0, f"Eval Error: {e}"
        return {"instance_id": instance_id, "score": score, "pred_sql": pred_sql_query, "error_info": error_info}

    def run_generalized_evaluation(self, args, temp_path: Path):
        # Implementation logic moved from evaluate_generalized
        gold_dir = args.gold_dir
        gold_exec_dir = args.gold_exec_dir or os.path.join(gold_dir, "spider2_gold", "exec_result")
        pred_result_dir = args.result_dir
        
        eval_jsonl = args.eval_jsonl or os.path.join(gold_dir, "spider2_gold", "spider2lite_eval.jsonl")
        eval_standard_dict = {}
        if os.path.exists(eval_jsonl):
            with open(eval_jsonl, 'r') as f:
                for line in f:
                    item = json.loads(line)
                    eval_standard_dict[item["instance_id"]] = item
        
        meta_jsonl = args.meta_jsonl # Mandatory for SQLite mapping usually
        metadata_dict = {}
        if meta_jsonl and os.path.exists(meta_jsonl):
            with open(meta_jsonl, 'r') as f:
                for line in f:
                    item = json.loads(line)
                    metadata_dict[item["instance_id"]] = item

        db_dir = Path(args.db_dir) if args.db_dir else Path("resources/spider2-localdb")
        result_csv_dir = f"{pred_result_dir}_csv" if args.mode == "sql" else None
        
        pred_ids = []
        if os.path.exists(pred_result_dir):
            ext = ".sql" if args.mode == "sql" else ".csv"
            pred_ids = [Path(f).stem for f in os.listdir(pred_result_dir) if f.endswith(ext)]
        
        eval_ids = sorted(set(eval_standard_dict.keys()).intersection(pred_ids)) if eval_standard_dict else pred_ids
        
        results = []
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(
                    self.evaluate_single_sql_instance, id, eval_standard_dict, metadata_dict, 
                    pred_result_dir, gold_exec_dir, temp_path, result_csv_dir, db_dir
                ): id for id in eval_ids
            }
            for future in tqdm(as_completed(futures), total=len(eval_ids), desc="Evaluating"):
                results.append(future.result())
        
        results.sort(key=lambda x: x["instance_id"])
        correct = sum(r["score"] for r in results)
        total = len(results)
        accuracy = correct / total if total > 0 else 0
        
        summary = {
            "correct": correct,
            "total": total,
            "accuracy": accuracy,
            "results": results
        }
        
        # Save summary to pred_result_dir
        if os.path.exists(pred_result_dir):
            summary_path = Path(pred_result_dir).parent / "evaluation_summary.json"
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=4)
            print(f"\n[OK] Evaluation summary saved to: {summary_path}")

        print(f"\n--- SUMMARY ---\nCorrect: {correct}\nTotal: {total}\nAccuracy: {accuracy:.4f}")
        return results
