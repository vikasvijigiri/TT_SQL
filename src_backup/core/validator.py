from core.logger import Logger

class Validator:
    """
    Validates execution results (Step 10).
    Check:
    - empty result
    - constraint mismatch
    """

    def check(self, result) -> bool:
        if result.error_message:
            return False
        
        if result.row_count == 0:
            Logger.log("Validation Failed: Empty result set.", level="WARN")
            return False
            
        # Placeholder for constraint mismatch check
        return True

def compute_confidence(scores: list[float], valid: bool) -> float:
    """
    Computes confidence (Step 11).
    """
    if not scores:
        return 0.0
        
    base = sum(scores) / len(scores)
    if not valid:
        base *= 0.5
    return base
