"""
Process-level LLM token usage monitor.

The existing thread-local counter in llm.py tracks tokens per-request for
cost reporting.  This module adds a process-wide aggregate so operators can
observe cumulative LLM spend across all threads and calls without reading
per-request logs.

Wire-in: call ``record_call(in_t, out_t)`` once per successful LLM response
in ``llm.py``'s ``generate()`` and ``agenerate()`` methods.

Exposed via ``get_token_stats()`` -> included in ``/api/performance`` response.
"""

import threading
from collections import defaultdict
from typing import Optional

_lock = threading.Lock()
_total_input: int = 0
_total_output: int = 0
_total_calls: int = 0

# Per-component breakdown: component_name -> {input, output, calls}
_component_stats: dict = defaultdict(lambda: {"input": 0, "output": 0, "calls": 0})


def record_call(
    input_tokens: int,
    output_tokens: int,
    component: Optional[str] = None,
) -> None:
    """Accumulate token counts from one completed LLM call.

    Pass *component* (e.g. "schema_linker", "sql_generator", "self_corrector",
    "result_validator", "answer_extractor") for per-agent breakdowns exposed via
    ``get_token_stats()``.
    """
    global _total_input, _total_output, _total_calls
    with _lock:
        _total_input += input_tokens
        _total_output += output_tokens
        _total_calls += 1
        if component:
            _component_stats[component]["input"] += input_tokens
            _component_stats[component]["output"] += output_tokens
            _component_stats[component]["calls"] += 1


def get_token_stats() -> dict:
    """Return a snapshot of cumulative LLM token usage including per-component breakdown."""
    with _lock:
        total = _total_input + _total_output
        calls = _total_calls
        breakdown = {
            k: {
                "input_tokens": v["input"],
                "output_tokens": v["output"],
                "total_tokens": v["input"] + v["output"],
                "calls": v["calls"],
            }
            for k, v in _component_stats.items()
        }
    return {
        "total_calls": calls,
        "total_input_tokens": _total_input,
        "total_output_tokens": _total_output,
        "total_tokens": total,
        "avg_tokens_per_call": round(total / calls, 1) if calls > 0 else None,
        "per_component": breakdown,
    }


def reset() -> None:
    """Reset all counters (intended for tests only)."""
    global _total_input, _total_output, _total_calls
    with _lock:
        _total_input = 0
        _total_output = 0
        _total_calls = 0
        _component_stats.clear()
