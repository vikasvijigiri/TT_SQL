import re
from typing import List, Any
from agent.app.models.schemas import SemanticColumn
from agent.app.utils.logger import logger


class SampleSuppressor:
    """
    Enterprise Sample Value Suppression Layer.
    Suppresses sample values for continuous floats, QC metrics, random IDs,
    and large numeric magnitudes while preserving discrete categorical enums, booleans,
    dialect-sensitive date/timestamp structures, and small discrete domains.
    """

    QC_KEYWORDS = [
        "qc",
        "quality",
        "score",
        "metric",
        "stat",
        "stddev",
        "variance",
        "mean",
        "avg",
        "p_val",
        "coverage",
    ]
    ID_KEYWORDS = ["id", "uuid", "hash", "key", "guid", "token"]

    @classmethod
    def _is_qc_or_metric(cls, col_name: str) -> bool:
        lower_name = col_name.lower()
        pattern = r"\b(?:qc|quality|score|metric|stat|stddev|variance|mean|avg|p_val|coverage)\b"
        return bool(re.search(pattern, lower_name))

    @classmethod
    def _is_uninformative_id(cls, col_name: str, sample_vals: List[Any]) -> bool:
        lower_name = col_name.lower()
        is_id = any(kw in lower_name for kw in cls.ID_KEYWORDS)
        if not is_id:
            return False

        # Check if values look like UUIDs, hashes, or large integer sequences
        for val in sample_vals:
            v_str = str(val).strip()
            # If it's a UUID/hash or long numeric string
            if (
                len(v_str) >= 16
                or re.match(r"^[0-9a-fA-F]{32}$", v_str)
                or re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-", v_str)
            ):
                return True
        return False

    @classmethod
    def _is_large_numeric_magnitude(cls, sample_vals: List[Any]) -> bool:
        for val in sample_vals:
            try:
                num = float(val)
                if abs(num) > 1_000_000 or (
                    isinstance(val, float) and val != round(val, 2)
                ):
                    return True
            except (ValueError, TypeError):
                continue
        return False

    @classmethod
    def _is_date_or_timestamp(
        cls, col_name: str, col_type: str, sample_vals: List[Any]
    ) -> bool:
        c_type = col_type.upper()
        if any(t in c_type for t in ("DATE", "TIME", "TIMESTAMP")):
            return True
        lower_name = col_name.lower()
        if any(
            kw in lower_name for kw in ("date", "time", "created", "updated", "epoch")
        ):
            return True
        for val in sample_vals[:2]:
            v_str = str(val).strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}", v_str) or re.match(
                r"^\d{2}/\d{2}/\d{4}", v_str
            ):
                return True
        return False

    @classmethod
    def smart_sample_selection(
        cls, column: SemanticColumn, max_samples: int = 3
    ) -> List[str]:
        """
        Evaluates a column's metadata and sample values to decide whether samples should be
        suppressed or retained for LLM reasoning.
        """
        vals = column.sample_values
        if not vals:
            return []

        col_name = column.name
        col_type = column.type.upper()

        # 1. Retain Booleans explicitly
        if len(vals) <= 2 and any(
            str(v).lower() in ("true", "false", "0", "1", "t", "f", "yes", "no")
            for v in vals
        ):
            return [str(v) for v in vals[:max_samples]]

        # 2. Retain Dialect-Sensitive Dates/Timestamps to clarify formatting (keep 2)
        if cls._is_date_or_timestamp(col_name, col_type, vals):
            return [str(v) for v in vals[: min(2, max_samples)]]

        # 3. Suppress QC metrics, random statistics, and large numeric magnitudes
        if cls._is_qc_or_metric(col_name):
            logger.debug(
                f"[SampleSuppressor] Suppressing QC/metric samples for column '{col_name}'."
            )
            return []

        if cls._is_uninformative_id(col_name, vals):
            logger.debug(
                f"[SampleSuppressor] Suppressing uninformative ID samples for column '{col_name}'."
            )
            return []

        if (
            "FLOAT" in col_type
            or "DOUBLE" in col_type
            or cls._is_large_numeric_magnitude(vals)
        ):
            # If it's a small discrete categorical domain that happens to be numeric (e.g. rating 1, 2, 3), keep
            unique_count = len(set(vals))
            if unique_count <= 5 and all(
                isinstance(v, (int, float)) and v == round(v) for v in vals[:5]
            ):
                return [str(v) for v in vals[:max_samples]]
            logger.debug(
                f"[SampleSuppressor] Suppressing continuous/large float samples for column '{col_name}'."
            )
            return []

        # 4. Retain Categorical Enums and Small Discrete Domains
        clean = []
        for val in vals:
            v_str = str(val).strip()
            if not v_str or len(v_str) > 60:  # Drop huge text blobs
                continue
            if v_str not in clean:
                clean.append(v_str)
            if len(clean) >= max_samples:
                break

        return clean
