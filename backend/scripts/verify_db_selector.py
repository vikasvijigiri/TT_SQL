"""Verify DB selector for stockindex all 3 queries + stockmarket regression."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.dab.dab_orchestrator import (
    _tokenize, _score_db_for_query, _count_numeric_columns, _get_column_names_quickly
)

si_base = Path(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockindex\query_dataset')
sm_base = Path(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset')

tests = [
    {
        "label": "stockindex q1 (expect DuckDB indextrade)",
        "question": "Which stock index in the Asia region has exhibited the highest average intraday volatility since 2020?",
        "cfgs": [
            {"name": "indextrade_database", "db_type": "duckdb", "db_path": str(si_base / "indextrade_query.db")},
            {"name": "indexinfo_database",  "db_type": "sqlite", "db_path": str(si_base / "indexInfo_query.db")},
        ],
        "expect": "indextrade",
    },
    {
        "label": "stockindex q2 (expect DuckDB indextrade)",
        "question": "Among North American stock indices, which indices had more up days than down days in 2018?",
        "cfgs": [
            {"name": "indextrade_database", "db_type": "duckdb", "db_path": str(si_base / "indextrade_query.db")},
            {"name": "indexinfo_database",  "db_type": "sqlite", "db_path": str(si_base / "indexInfo_query.db")},
        ],
        "expect": "indextrade",
    },
    {
        "label": "stockindex q3 (expect DuckDB indextrade)",
        "question": "If an investor had made regular monthly investments in all indices since 2000, which 5 indices would have produced the highest overall returns, and what countries do they belong to?",
        "cfgs": [
            {"name": "indextrade_database", "db_type": "duckdb", "db_path": str(si_base / "indextrade_query.db")},
            {"name": "indexinfo_database",  "db_type": "sqlite", "db_path": str(si_base / "indexInfo_query.db")},
        ],
        "expect": "indextrade",
    },
    {
        "label": "stockmarket q1 (expect DuckDB stocktrade)",
        "question": "What is the total trading volume for Apple stock on 2023-11-01?",
        "cfgs": [
            {"name": "stocktrade_query", "db_type": "duckdb", "db_path": str(sm_base / "stocktrade_query.db")},
            {"name": "stockinfo_query",  "db_type": "sqlite", "db_path": str(sm_base / "stockinfo_query.db")},
        ],
        "expect": "stocktrade",
    },
    {
        "label": "stockmarket q2 (expect SQLite stockinfo)",
        "question": "How many stocks are listed on the NASDAQ exchange?",
        "cfgs": [
            {"name": "stocktrade_query", "db_type": "duckdb", "db_path": str(sm_base / "stocktrade_query.db")},
            {"name": "stockinfo_query",  "db_type": "sqlite", "db_path": str(sm_base / "stockinfo_query.db")},
        ],
        "expect": "stockinfo",
    },
]

print()
for test in tests:
    q_tokens = _tokenize(test["question"])
    scored = []
    for cfg in test["cfgs"]:
        db_path = cfg["db_path"]
        db_type = cfg["db_type"]
        s = _score_db_for_query(cfg, q_tokens)
        num_cols = _count_numeric_columns(db_path, db_type)
        total_cols = len(_get_column_names_quickly(db_path, db_type))
        scored.append((cfg["name"], s, num_cols, total_cols))

    scored.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    winner = scored[0][0]
    ok = test["expect"] in winner
    status = "OK  " if ok else "FAIL"
    print(f"[{status}] {test['label']}")
    for name, s, nc, tc in scored:
        print(f"        {name}: score={s:.1f}  numeric_cols={nc}  total_cols={tc}")
print()
