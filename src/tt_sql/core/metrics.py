import json
import os
import time
from typing import List, Dict, Any

class MetricsTracker:
    """
    Tracks and persists benchmark metrics (Accuracy, Latency, etc.)
    to 'results/metrics.json'.
    """
    
    def __init__(self, base_dir: str = None, model_name: str = None):
        if base_dir is None:
            # Avoid circular import if possible, or keep as is
            try:
                from .paths import RESULTS_BASE_DIR
                base = RESULTS_BASE_DIR
            except ImportError:
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            base = base_dir

        if model_name:
            safe_name = model_name.replace("/", "_").replace(":", "_")
            self.metrics_file = os.path.join(base, "results", safe_name, "metrics.json")
        else:
            # Fallback to global (legacy)
            self.metrics_file = os.path.join(base, "results", "metrics.json")
            
        # Ensure dir exists
        os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)

    def load_metrics(self) -> List[Dict[str, Any]]:
        """Load all historical metrics."""
        if not os.path.exists(self.metrics_file):
            return []
        try:
            with open(self.metrics_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading metrics: {e}")
            return []

    # Approximate Pricing (per 1M tokens) - can be refined later per model
    PRICING = {
        "default": {"input": 5.00, "output": 15.00},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "bedrock/openai.gpt-oss-safeguard-120b": {"input": 5.00, "output": 15.00} # Placeholder
    }

    def calculate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on model pricing."""
        # Normalize model name key (simple matching)
        pricing = self.PRICING.get("default")
        for key in self.PRICING:
            if key in model_name.lower():
                pricing = self.PRICING[key]
                break
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def save_run(self, 
                 model_name: str, 
                 accuracy: float, 
                 avg_latency: float, 
                 total_samples: int,
                 rag_source: str = "none",
                 use_rag: bool = False,
                 passed_count: int = 0,
                 failed_count: int = 0,
                 total_tokens: int = 0,
                 total_cost: float = 0.0,
                 batch_id: str = None):
        """Append a new run or update existing one if batch_id provided."""
        entries = self.load_metrics()
        
        # Helper to create/update entry dict
        def make_entry(existing=None):
            e = existing or {}
            if not existing:
                e["timestamp"] = time.time()
                e["date"] = time.strftime("%Y-%m-%d %H:%M:%S")
                if batch_id: e["batch_id"] = batch_id
            
            # Update fields
            e["model"] = model_name
            e["accuracy"] = accuracy
            e["avg_latency"] = avg_latency
            e["total_samples"] = total_samples
            e["rag_source"] = rag_source
            e["use_rag"] = use_rag
            e["passed"] = passed_count
            e["failed"] = failed_count
            e["total_tokens"] = total_tokens
            e["total_cost"] = total_cost
            return e

        if batch_id:
            # Try to find existing
            found_idx = -1
            for i, entry in enumerate(entries):
                if entry.get("batch_id") == batch_id:
                    found_idx = i
                    break
            
            if found_idx >= 0:
                entries[found_idx] = make_entry(entries[found_idx])
            else:
                entries.append(make_entry())
        else:
            # Legacy append
            entries.append(make_entry())
        
        try:
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except Exception as e:
            print(f"Error saving metrics: {e}")
