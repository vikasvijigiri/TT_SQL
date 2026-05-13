import json
import os
import re
import pickle
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple, Optional


# =========================
# DATA MODEL
# =========================

from src.core.models import CandidateColumn


# =========================
# UTILS
# =========================

def normalize(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    text = normalize(text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 2]


def ngrams(tokens: List[str], n=2) -> List[str]:
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]


def flatten_json(obj, prefix=""):
    paths = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}.{k}" if prefix else k
            paths.extend(flatten_json(v, new_key))
    elif isinstance(obj, list):
        for item in obj:
            paths.extend(flatten_json(item, prefix))
    else:
        paths.append((prefix, str(obj)))
    return paths


def simple_similarity(a: str, b: str) -> float:
    """Cheap fuzzy match (no heavy libs)"""
    a, b = normalize(a), normalize(b)
    if a in b or b in a:
        return 1.0
    return 0.0


# =========================
# MAIN INDEXER
# =========================

class SchemaIndexer:

    def __init__(self, metadata_path: str, cache_path: str = "scratch/schema.pkl"):
        self.metadata_path = metadata_path
        self.cache_path = cache_path

        # indexes
        self.token_index = defaultdict(list)
        self.value_index = defaultdict(list)
        self.value_token_index = defaultdict(list)
        self.phrase_index = defaultdict(list)
        self.structure_index = defaultdict(list)

        self.columns: Dict[str, CandidateColumn] = {}

    # =========================
    # LOAD + CACHE
    # =========================

    def load(self, force=False):
        if os.path.exists(self.cache_path) and not force:
            with open(self.cache_path, "rb") as f:
                data = pickle.load(f)
                self.__dict__.update(data)
            return

        with open(self.metadata_path) as f:
            data = json.load(f)

        tables = self._normalize_schema(data)

        for table in tables:
            self._process_table(table)

        self._save_cache()

    def _save_cache(self):
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "wb") as f:
            pickle.dump(self.__dict__, f)

    # =========================
    # SCHEMA NORMALIZATION
    # =========================

    def _normalize_schema(self, data):
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            if "tables" in data:
                return data["tables"]

            tables = []
            for k, v in data.items():
                if isinstance(v, dict):
                    v["name"] = k
                    tables.append(v)
            return tables

        return []

    # =========================
    # TABLE PROCESSING
    # =========================

    def _process_table(self, table):
        tname = table.get("name", "unknown")
        cols = table.get("columns", [])

        row_samples = table.get("sample", [])
        col_samples = defaultdict(list)

        for row in row_samples:
            if isinstance(row, dict):
                for k, v in row.items():
                    if v is not None:
                        col_samples[k].append(str(v))

        for col in cols:
            cname = col.get("name", col.get("column_name"))
            if not cname:
                continue

            samples = list(set(col.get("sample_values", []) + col_samples.get(cname, [])))[:50]

            json_paths = []
            for s in samples:
                try:
                    parsed = json.loads(s)
                    json_paths.extend(flatten_json(parsed))
                except:
                    pass

            stats = self._compute_stats(samples)

            candidate = CandidateColumn(
                table=tname,
                column=cname,
                dtype=col.get("type", ""),
                sample_values=samples,
                description=col.get("description", ""),
                is_array="ARRAY" in col.get("type", "").upper(),
                json_paths=[p for p, _ in json_paths],
                stats=stats
            )

            self.columns[candidate.fqn] = candidate

            self._index_column(candidate)

    # =========================
    # INDEXING
    # =========================

    def _index_column(self, col: CandidateColumn):

        # --- Token index ---
        tokens = tokenize(col.column) + tokenize(col.description)
        for t in tokens:
            self.token_index[t].append(col)

        # --- Phrase index ---
        for p in ngrams(tokens, 2):
            self.phrase_index[p].append(col)

        # --- Value index ---
        for v in col.sample_values:
            v_norm = normalize(v)

            self.value_index[v_norm].append(col)

            for tok in tokenize(v_norm):
                self.value_token_index[tok].append(col)

        # --- Structure index ---
        if col.is_array or col.json_paths:
            self.structure_index[col.table].append(col)

    # =========================
    # SEARCH (SCORING)
    # =========================

    def search(self, query: str, top_k=40):
        tokens = tokenize(query)
        phrases = ngrams(tokens, 2)

        scores = defaultdict(float)

        for t in tokens:
            for col in self.token_index.get(t, []):
                scores[col.fqn] += 1

        for p in phrases:
            for col in self.phrase_index.get(p, []):
                scores[col.fqn] += 2

        for t in tokens:
            for col in self.value_token_index.get(t, []):
                scores[col.fqn] += 3

        for v in tokens:
            for col in self.value_index.get(v, []):
                scores[col.fqn] += 4

        # fuzzy boost
        for col in self.columns.values():
            for v in col.sample_values:
                if simple_similarity(query, v):
                    scores[col.fqn] += 2

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return [(self.columns[k], score) for k, score in ranked[:top_k]]

    # =========================
    # STATS
    # =========================

    def _compute_stats(self, values: List[str]):
        if not values:
            return {}

        total = len(values)
        distinct = len(set(values))
        null_ratio = sum(1 for v in values if v in ["", "null", "none"]) / total

        return {
            "distinct_count": distinct,
            "null_ratio": null_ratio
        }