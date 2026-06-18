---
name: session-2026-06-18-improvements
description: Architecture improvements made on 2026-06-18 for speed, accuracy, and non-blocking execution
metadata:
  type: project
---

## Changes made 2026-06-18

### Bug fixes (all verified syntax-clean)

1. **`db_executor.py` — IndexSeeding `AttributeError` fix**
   `sqlite3.Row` supports `.keys()` but NOT `.get()`. Changed `hasattr(obj, "keys")` guard
   to `isinstance(col, dict)` only, then uses `col["name"]` key-access for `sqlite3.Row`.
   Verified: `[IndexSeeding] Created dynamic index` INFO lines appear (no more errors).

2. **`sql_critic_agent.py` — Execution probe captured wrong variable**
   `execute_direct` returns `(ok, err_msg, rows)`. The probe was capturing `_` for `err_msg`
   and using `rows` (empty `[]`) as the error string. Fixed to capture and forward `err_msg`.

3. **`sql_critic_agent.py` — Trailing semicolon broke subquery wrapping**
   Added `clean_sql = proposed_sql.rstrip().rstrip(";")` before wrapping in
   `SELECT * FROM ({clean_sql}) AS __probe LIMIT 1`.

4. **`sql_critic_agent.py` — Prompt Integrity Monitor**
   Critic now detects NL text passed as SQL and short-circuits with a safe no-op,
   logging `[PromptIntegrity] Critic received non-SQL input` at WARNING level.

### Performance improvements

5. **`orchestrator.py` — FeasibilityAgent parallelized with ContextPruner**
   Launched as `ThreadPoolExecutor` background future; collected before strategy routing.
   Saves ~1 serial LLM round-trip (~3-8s) per query.

6. **`orchestrator.py` — `dynamic_lessons.json` TTL cache**
   Module-level `_DYN_LESSONS_CACHE` with 60s TTL replaces per-query `json.load()` calls.

### Non-blocking async architecture

7. **`llm.py` — `agenerate_structured()` added**
   Async version of `generate_structured` using `await self.agenerate()` (`ainvoke` internally).
   Foundation for future full-async orchestrator pipeline.

8. **`dab_runner.py` — `--async` flag + `run_all_concurrent()` coroutine**
   `asyncio.gather()` + `ThreadPoolExecutor(max_workers=len(work))` lets all queries run
   concurrently on ONE Python process (vs. N separate processes).
   Evidence: 195 log entries/second at peak (17 threads overlapping I/O waits).
   Usage: `python -m agent.app.dab.dab_runner --all --skip_docker --async`

### Monitoring

- `check_dab_results.ps1` — status script showing PASS/FAIL, IndexSeeding warnings,
  probe errors, and peak concurrency (log lines/second).

**Why:** Goal is 0 bias, 0 IndexSeeding crashes, 0 PromptIntegrity failures,
minimal latency via non-blocking I/O, 100% SQL validation.
