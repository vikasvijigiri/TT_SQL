"""
Process-level LLM token usage monitor.

The existing thread-local counter in llm.py tracks tokens per-request for
cost reporting.  This module adds a process-wide aggregate so operators can
observe cumulative LLM spend across all threads and calls without reading
per-request logs.

Wire-in: call ``record_call(in_t, out_t)`` once per successful LLM response
in ``llm.py``'s ``generate()`` and ``agenerate()`` methods.

Exposed via ``get_token_stats()`` → included in ``/api/performance`` response.
"""

import threading

_lock = threading.Lock()
_total_input: int = 0
_total_output: int = 0
_total_calls: int = 0


def record_call(input_tokens: int, output_tokens: int) -> None:
    """Accumulate token counts from one completed LLM call."""
    global _total_input, _total_output, _total_calls
    with _lock:
        _total_input += input_tokens
        _total_output += output_tokens
        _total_calls += 1


def get_token_stats() -> dict:
    """
    Return a snapshot of cumulative LLM token usage for this process.

    ``avg_tokens_per_call`` is None until at least one call has completed.
    """
    with _lock:
        total = _total_input + _total_output
        calls = _total_calls
    return {
        "total_calls": calls,
        "total_input_tokens": _total_input,
        "total_output_tokens": _total_output,
        "total_tokens": total,
        "avg_tokens_per_call": round(total / calls, 1) if calls > 0 else None,
    }


def reset() -> None:
    """Reset all counters (intended for tests only)."""
    global _total_input, _total_output, _total_calls
    with _lock:
        _total_input = 0
        _total_output = 0
        _total_calls = 0
