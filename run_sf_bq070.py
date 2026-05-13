"""
Targeted runner for sf_bq070 against IDC.IDC_V17.DICOM_ALL
"""
import json
import os
import sys

sys.path.insert(0, ".")

from src.core.orchestrator import SemanticDINOrchestrator
from src.utils.logger import logger

INSTANCE_ID  = "sf_bq070"
DB_NAME      = "IDC"
DB_PATH      = "resources/databases/snowflake/IDC/IDC_V17"
DIALECT      = "snowflake"

# The benchmark question
QUESTION = (
    "Could you provide a clean, structured dataset from dicom_all table that only includes "
    "SM images marked as VOLUME from the TCGA-LUAD and TCGA-LUSC collections, excluding any "
    "slides with compression type \u201cother,\u201d where the specimen preparation step explicitly "
    "has \u201cEmbedding medium\u201d set to \u201cTissue freezing medium,\u201d and ensuring that the tissue "
    "type is only \u201cnormal\u201d or \u201ctumor\u201d and the cancer subtype is reported accordingly?"
)

save_dir = os.path.join("results", DB_NAME)
os.makedirs(save_dir, exist_ok=True)

logger.start_live_task_log(os.path.join(save_dir, f"{INSTANCE_ID}.md"))

try:
    orchestrator = SemanticDINOrchestrator(
        db_directory=DB_PATH,
        db_name=DB_NAME,
        dialect=DIALECT,
        max_retries=3,           # allow 3 correction attempts for this complex query
    )

    final_sql = orchestrator.execute_query(QUESTION, instance_id=INSTANCE_ID)

    # Save SQL
    sql_path = os.path.join(save_dir, f"{INSTANCE_ID}.sql")
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(final_sql)
    logger.success(f"Saved {INSTANCE_ID}.sql")

    # Check CSV
    csv_path = os.path.join(save_dir, f"{INSTANCE_ID}.csv")
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 30:
        import pandas as pd
        df = pd.read_csv(csv_path)
        logger.success(f"CSV has {len(df)} rows x {len(df.columns)} columns")
        print(df.head(3).to_string())
    else:
        logger.warning("CSV is empty or missing — execution may have failed.")

finally:
    logger.stop_live_task_log()
