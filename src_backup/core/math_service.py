import decimal
from decimal import Decimal
from typing import Any, List, Dict
import math

class MathService:
    """
    Provides high-precision mathematical operations for the agentic pipeline.
    Uses Python's Decimal library to avoid floating point inaccuracies.
    """
    
    @staticmethod
    def calculate(expression: str, precision: int = 10) -> str:
        """
        Evaluates a simple mathematical expression with high precision.
        """
        try:
            # Set precision
            decimal.getcontext().prec = precision
            # Replace common functions with math equivalents if needed
            # For now, we trust basic operators and Decimal conversion
            # We use a safe eval-like approach or simple parsing
            # For the prototype, we'll use a controlled eval for math
            allowed_names = {
                "Decimal": Decimal,
                "math": math,
                "abs": abs,
                "round": round,
                "sum": sum,
                "max": max,
                "min": min
            }
            # Remove any potentially dangerous characters
            clean_expr = expression.replace("__", "")
            result = eval(clean_expr, {"__builtins__": {}}, allowed_names)
            return str(result)
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def aggregate(values: List[float], op: str = "sum") -> str:
        """
        Performs accurate aggregation on a list of numbers.
        """
        try:
            decimal_values = [Decimal(str(v)) for v in values]
            if op == "sum":
                return str(sum(decimal_values))
            elif op == "avg":
                return str(sum(decimal_values) / len(decimal_values))
            elif op == "max":
                return str(max(decimal_values))
            elif op == "min":
                return str(min(decimal_values))
            return "Error: Unsupported operation"
        except Exception as e:
            return f"Error: {str(e)}"
