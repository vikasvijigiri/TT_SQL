import os
import pandas as pd
from typing import List, Dict, Any
from app.services.utils.logger import Logger

class FailureService:
    def __init__(self, evaluation_service):
        self.evaluation_service = evaluation_service

    def collect_failures(self, eval_results: List[Dict[str, Any]], output_path: str = "failed_ids.csv") -> List[str]:
        """Filters failed instances from evaluation results and saves their IDs to a CSV."""
        failed_ids = [r["instance_id"] for r in eval_results if r.get("score") != 1]
        
        if failed_ids:
            pd.DataFrame({"instance_id": failed_ids}).to_csv(output_path, index=False)
            Logger.log(f"Found {len(failed_ids)} failed examples. Saved to {output_path}")
        else:
            Logger.log("No failures found! All examples passed.")
            pd.DataFrame({"instance_id": []}).to_csv(output_path, index=False)
            
        return failed_ids

    def identify_regressions(self, current_results: List[Dict[str, Any]], baseline_results: List[Dict[str, Any]]) -> List[str]:
        """Identifies instances that passed in baseline but failed in current results."""
        baseline_passed = {r["instance_id"] for r in baseline_results if r.get("score") == 1}
        current_failed = {r["instance_id"] for r in current_results if r.get("score") != 1}
        
        regressions = sorted(list(baseline_passed.intersection(current_failed)))
        Logger.log(f"Identified {len(regressions)} regressions.")
        return regressions
