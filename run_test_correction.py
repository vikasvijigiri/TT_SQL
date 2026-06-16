from src.utils.logger import logger
from src.core.orchestrator import SemanticDINOrchestrator
import os

def run():
    # Force the log file path
    os.makedirs("results/IDC", exist_ok=True)
    logger.start_live_task_log("results/IDC/test_correction_log.txt")
    
    try:
        orchestrator = SemanticDINOrchestrator(
            db_directory="resources/databases/snowflake/IDC/IDC_V17",
            db_name="IDC",
            dialect="snowflake",
            max_retries=3
        )
        
        # This query is designed to trip up the initial SQL generation.
        # We ask for a strict EXACT match that we know fails case sensitivity.
        # We also ask to exclude "other" without mentioning nulls, to see if it drops rows.
        query = "Could you provide a dataset from dicom_all that only includes SM images from the TCGA-LUAD collection, where SpecimenDescriptionSequence contains the EXACT WORD 'TUMOR' in all caps?"
        
        logger.log_section("TESTING 0-ROW CORRECTION LOOP", color=logger.YELLOW)
        orchestrator.execute_query(query, instance_id="test_correction")
        
    finally:
        logger.stop_live_task_log()

if __name__ == "__main__":
    run()
