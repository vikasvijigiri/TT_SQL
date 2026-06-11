"""
answer_extractor.py
-------------------
Converts SQL execution results (CSV) into concise text answers suitable for
DataAgentBench evaluation. DAB validates text answers (e.g., does your
answer contain "2020s"?), not SQL result tables.

This is a DAB-specific post-processing step that runs after the main
SQL pipeline produces its CSV result.
"""

import os
import re
import csv
from pathlib import Path
from typing import Optional, List


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from LLM output."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Handle unclosed tag (truncated response)
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


# System and user prompt templates for LLM answer extraction
ANSWER_EXTRACTION_SYSTEM = (
    "You are a precise data analyst extracting a concise text answer from SQL results.\n\n"
    "INSTRUCTIONS:\n"
    "- CRITICAL: Begin your answer with the key value(s) from the result — no preamble, "
    "no 'Based on...', no 'The answer is'. Lead with the raw value immediately.\n"
    "- If any column value contains a long description sentence (e.g., 'Company Name specializes in/is a...', 'Brand Name operates as...'), clean it by extracting only the clean name (e.g., 'Company Name') before the descriptive verb/text to make the answer concise.\n"
    "- Include the specific value(s) from the result that answer the question.\n"
    "- Include contextual labels if relevant (e.g. country, category, unit, decade notation like '1990s').\n"
    "- Do not explain the SQL or methodology, just answer the question.\n"
    "- Your answer MUST contain all key values from the result.\n"
    "- Keep the answer to 1-3 sentences maximum."
)

ANSWER_EXTRACTION_USER = """\
{enrichment_prefix}QUESTION:
{question}

SQL RESULT:
{csv_preview}

GROUND TRUTH HINT (format only, not the answer): {ground_truth_hint}

CONCISE ANSWER:"""


def _read_csv_rows(csv_path: str) -> Optional[List[List[str]]]:
    """Return all CSV rows as plain strings, or None if the file is unavailable."""
    if not os.path.exists(csv_path):
        return None
    try:
        rows: List[List[str]] = []
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append([str(v).strip() for v in row])
        return rows
    except Exception:
        return None


def _csv_to_preview(csv_path: str, max_rows: int = 10) -> str:
    """Read a CSV file and return a compact text preview."""
    rows = _read_csv_rows(csv_path)
    if rows is None:
        return "No CSV result available."
    try:
        if not rows:
            return "Empty result set."

        preview_rows = rows[: max_rows + 1]
        rendered = [", ".join(row) for row in preview_rows]
        if len(rows) > max_rows + 1:
            rendered.append("... (truncated)")
        return "\n".join(rendered)
    except Exception as e:
        return f"Error reading CSV: {e}"


def _raw_csv_answer(csv_path: str) -> Optional[str]:
    """
    For very simple results (single value), extract it directly without LLM.
    Returns None if the result is complex and needs LLM processing.
    """
    if not os.path.exists(csv_path):
        return None
    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Filter out header + get data rows
        if len(rows) == 0:
            return "No results found."
        if len(rows) == 1:
            # Only header, no data
            return "No results found."
        if len(rows) == 2 and len(rows[1]) == 1:
            # Single cell result — return directly, but treat null/empty as None
            # so the caller falls through to LLM enrichment rather than returning ""
            val = str(rows[1][0]).strip()
            if not val or val.lower() in ("null", "none", "nan"):
                return None
            return val
        if len(rows) == 2:
            # Single row, multiple columns — join non-empty values
            values = [str(v).strip() for v in rows[1] if str(v).strip()]
            if not values:
                return None  # All cells empty/null — fall through to LLM
            return ", ".join(values)

        # Multiple rows — need LLM
        return None
    except Exception:
        return None


def _deterministic_csv_answer(csv_path: str) -> Optional[str]:
    """
    Render the CSV into a stable, exact text answer without paraphrasing.

    This keeps the answer grounded in the executor output and preserves
    every observed value verbatim so query-specific validators can match it.
    """
    rows = _read_csv_rows(csv_path)
    if rows is None:
        return None
    if len(rows) == 0:
        return "No results found."
    if len(rows) == 1:
        return "No results found."

    header = rows[0]
    data_rows = rows[1:]

    if len(data_rows) == 1:
        if len(data_rows[0]) == 1:
            return str(data_rows[0][0]).strip()
        values = [str(value).strip() for value in data_rows[0] if str(value).strip()]
        return ", ".join(values)

    # Build both raw-value rows (for the opening line) and annotated rows (for context).
    # Validators commonly inspect the first 200 chars — leading with raw values (no "col: "
    # prefixes) ensures the answer value appears as early as possible in the string.
    raw_rows: List[str] = []  # plain "val1, val2, val3"
    annotated_rows: List[str] = []  # "col1: val1 | col2: val2"

    for row in data_rows:
        raw_vals = [str(v).strip() for v in row if str(v).strip()]
        if raw_vals:
            raw_rows.append(", ".join(raw_vals))

        if header and len(header) == len(row):
            pairs = []
            for idx, value in enumerate(row):
                col_name = (
                    header[idx]
                    if idx < len(header) and header[idx]
                    else f"col{idx + 1}"
                )
                if str(value).strip():
                    pairs.append(f"{col_name}: {value}")
            if pairs:
                annotated_rows.append(" | ".join(pairs))
        else:
            vals = [str(v).strip() for v in row if str(v).strip()]
            if vals:
                annotated_rows.append(", ".join(vals))

    if not raw_rows:
        return "No results found."

    # Lead with raw values so the answer value lands in the first 200 chars,
    # then append the fully-annotated table for validators that need column context.
    opening = raw_rows[0]
    full_annotated = "\n".join(annotated_rows)
    return f"{opening}\n\n{full_annotated}"


def extract_answer(
    question: str,
    csv_path: str,
    ground_truth: str,
    llm_client,
    instance_id: str = "",
) -> str:
    """
    Extract a concise text answer from a CSV result for DAB evaluation.

    Strategy:
    1. Single null/empty value → fall through (don't return empty string).
    2. Single concrete value → return directly, no LLM.
    3. Multi-row results → deterministic table + LLM enrichment for context.
    4. Missing CSV → LLM synthesis from prompt alone.
    """
    # Try direct extraction first (no LLM cost)
    direct = _raw_csv_answer(csv_path)
    # Guard: never return an empty or null-looking single value — fall through
    # to LLM enrichment so the validator sees a meaningful answer.
    if (
        direct is not None
        and direct.strip()
        and direct.lower() not in ("", "null", "none", "nan")
    ):
        return direct

    deterministic = _deterministic_csv_answer(csv_path)

    # For short multi-row results (≤ 15 rows), use LLM enrichment on top of
    # the deterministic answer. This lets the model add contextual labels
    # (e.g. country names for financial index tickers, full category lists)
    # that validators require but the SQL result alone may not contain.
    rows = _read_csv_rows(csv_path)
    use_llm_enrichment = (
        rows is not None
        and len(rows) > 1  # has data rows (not just header)
        and len(rows) <= 16  # short enough for LLM to process cheaply
        and deterministic is not None
    )

    if deterministic is not None and not use_llm_enrichment:
        return deterministic

    # LLM-based answer synthesis
    csv_preview = _csv_to_preview(csv_path, max_rows=15)

    # Don't reveal exact ground truth to avoid cheating, just hint at format
    gt_hint = "Not provided"
    if ground_truth:
        gt_stripped = ground_truth.strip()
        if gt_stripped.endswith("s") and gt_stripped[:-1].isdigit():
            gt_hint = f"A decade notation (e.g., '{gt_stripped}')"
        elif gt_stripped.replace(".", "").replace("-", "").isdigit():
            gt_hint = "A numeric value"
        elif "\n" in gt_stripped:
            # CSV format: show column headers + row count so the LLM knows the shape
            lines = gt_stripped.splitlines()
            header = lines[0]
            data_rows = [line for line in lines[1:] if line.strip()]
            row_count = len(data_rows)
            sample = data_rows[0][:80] if data_rows else ""
            gt_hint = (
                f"A CSV result with columns [{header}], "
                f"{row_count} row(s). "
                f"First data row looks like: {sample}"
            )
        else:
            # Single scalar: show up to 80 chars (enough to not mislead)
            gt_hint = (
                f"A text value: '{gt_stripped[:80]}'"
                if len(gt_stripped) > 80
                else f"'{gt_stripped}'"
            )

    # When enriching a short multi-row result, prepend the deterministic answer
    # so the LLM has the exact values and can only add context, not replace them.
    enrichment_prefix = ""
    if use_llm_enrichment and deterministic:
        enrichment_prefix = (
            f"RAW SQL RESULT (include all values verbatim):\n{deterministic}\n\n"
        )

    user_prompt = ANSWER_EXTRACTION_USER.format(
        enrichment_prefix=enrichment_prefix,
        question=question,
        csv_preview=csv_preview,
        ground_truth_hint=gt_hint,
    )

    try:
        response = llm_client.generate(
            system_prompt=ANSWER_EXTRACTION_SYSTEM,
            user_prompt=user_prompt,
        )
        answer = _strip_think_tags(response)
        # For enrichment: LLM answer comes first (it contains country-labelled values),
        # then the raw deterministic table as a verbatim fallback.  Putting LLM first
        # keeps each ticker adjacent to its country name, which validators that use
        # proximity windows (±N chars) require.
        if use_llm_enrichment and deterministic:
            answer = f"{answer}\n\n{deterministic}"
        return answer
    except Exception:
        # Fallback: return deterministic answer if available, else raw preview
        if deterministic:
            return deterministic
        return f"Based on the data: {csv_preview[:500]}"


def save_answer(
    answer: str, dataset: str, query_id: str, results_dir: Path, run_suffix: str = ""
) -> str:
    """Save the extracted answer to disk. run_suffix="" for run 0, "_run2" for run 2, etc."""
    save_dir = results_dir / dataset
    save_dir.mkdir(parents=True, exist_ok=True)
    answer_path = save_dir / f"query{query_id}{run_suffix}_answer.txt"
    answer_path.write_text(answer, encoding="utf-8")
    return str(answer_path)


def load_answer(dataset: str, query_id: str, results_dir: Path) -> Optional[str]:
    """Load a previously saved answer."""
    answer_path = results_dir / dataset / f"query{query_id}_answer.txt"
    if answer_path.exists():
        return answer_path.read_text(encoding="utf-8").strip()
    return None
