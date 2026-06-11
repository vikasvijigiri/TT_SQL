"""
Unit tests for TT_SQL_V2 pipeline components.

Run with:
    pytest backend/tests/test_pipeline_units.py -v
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# SystemPromptCompactor — dialect cast rules
# ---------------------------------------------------------------------------
class TestSystemPromptCompactor(unittest.TestCase):
    def _compact(self, dialect: str) -> str:
        from backend.app.core.prompts.system_prompt_compactor import (
            SystemPromptCompactor,
        )

        # Use a short raw prompt that won't trigger the "preserve" guard
        return SystemPromptCompactor.compact(
            "high-precision enterprise SQL agent", dialect
        )

    def test_sqlite_uses_cast_syntax(self):
        out = self._compact("sqlite")
        self.assertIn("CAST(expr AS INTEGER|REAL|TEXT|BLOB)", out)

    def test_snowflake_uses_double_colon(self):
        out = self._compact("snowflake")
        self.assertIn("::", out)

    def test_postgres_uses_double_colon(self):
        out = self._compact("postgres")
        self.assertIn("::", out)

    def test_mysql_uses_cast_char(self):
        out = self._compact("mysql")
        self.assertIn("CAST(expr AS CHAR", out)

    def test_mssql_uses_cast_or_convert(self):
        out = self._compact("mssql")
        self.assertIn("CONVERT", out)

    def test_duckdb_uses_cast_or_colon(self):
        out = self._compact("duckdb")
        self.assertIn("CAST(expr AS TYPE)", out)

    def test_unknown_dialect_falls_back_to_cast(self):
        out = self._compact("somefuturedb")
        self.assertIn("CAST(expr AS TYPE)", out)


# ---------------------------------------------------------------------------
# ReasoningDepthController — dialect-specific addendums
# ---------------------------------------------------------------------------
class TestReasoningDepthController(unittest.TestCase):
    def _get_directives(self, dialect: str, **profile_flags) -> list:
        from backend.app.core.prompts.reasoning_depth_controller import (
            ReasoningDepthController,
        )
        from backend.app.core.query_analysis.capability_detector import (
            QueryCapabilityProfile,
        )

        profile = QueryCapabilityProfile(
            requires_joins=profile_flags.get("requires_joins", False),
            requires_aggregation=profile_flags.get("requires_aggregation", True),
            requires_windows=profile_flags.get("requires_windows", False),
            requires_variants=profile_flags.get("requires_variants", False),
            requires_timestamps=profile_flags.get("requires_timestamps", True),
        )
        return ReasoningDepthController.get_directives(
            "some query word word word word", profile, dialect=dialect
        )

    def test_sqlite_addendum_present(self):
        directives = self._get_directives("sqlite", requires_aggregation=True)
        combined = " ".join(directives)
        self.assertIn("SQLite", combined)
        self.assertIn("CAST", combined)

    def test_duckdb_addendum_present(self):
        directives = self._get_directives("duckdb")
        combined = " ".join(directives)
        self.assertIn("DuckDB", combined)

    def test_postgres_addendum_present(self):
        directives = self._get_directives("postgres")
        combined = " ".join(directives)
        self.assertIn("INTERVAL", combined)

    def test_mysql_addendum_present(self):
        directives = self._get_directives("mysql")
        combined = " ".join(directives)
        self.assertIn("MySQL", combined)

    def test_snowflake_no_extra_addendum(self):
        # Snowflake has no special addendum — should not crash
        directives = self._get_directives("snowflake")
        self.assertTrue(len(directives) >= 2)


# ---------------------------------------------------------------------------
# ProfilerAgent._cast_to_text — dialect-aware probe SQL casts
# ---------------------------------------------------------------------------
class TestProfilerAgentCastToText(unittest.TestCase):
    def setUp(self):
        from backend.app.agents.profiler_agent import ProfilerAgent

        self.cast = ProfilerAgent._cast_to_text

    def test_postgres_double_colon(self):
        self.assertEqual(self.cast("col", "postgres"), "col::text")

    def test_redshift_double_colon(self):
        self.assertEqual(self.cast("col", "redshift"), "col::text")

    def test_oracle_to_char(self):
        self.assertIn("TO_CHAR", self.cast("col", "oracle"))

    def test_sqlite_cast_varchar(self):
        result = self.cast("col", "sqlite")
        self.assertIn("CAST", result)
        self.assertIn("VARCHAR", result)

    def test_snowflake_cast_varchar(self):
        result = self.cast("col", "snowflake")
        self.assertIn("CAST", result)


# ---------------------------------------------------------------------------
# SchemaRetriever — synonym expansion
# ---------------------------------------------------------------------------
class TestSchemaRetrieverSynonyms(unittest.TestCase):
    def setUp(self):
        from backend.app.core.retrieval.schema_retriever import SchemaRetriever

        self.retriever = SchemaRetriever()

    def test_revenue_expands_to_sales(self):
        tokens = self.retriever._tokenize("revenue")
        expanded = self.retriever._expand_with_synonyms(tokens)
        self.assertIn("sales", expanded)

    def test_customer_expands_to_user(self):
        tokens = self.retriever._tokenize("customer")
        expanded = self.retriever._expand_with_synonyms(tokens)
        self.assertIn("user", expanded)

    def test_unknown_word_no_expansion(self):
        tokens = self.retriever._tokenize("xyzabc123")
        expanded = self.retriever._expand_with_synonyms(tokens)
        self.assertEqual(tokens, expanded)

    def test_expansion_is_superset(self):
        tokens = self.retriever._tokenize("order")
        expanded = self.retriever._expand_with_synonyms(tokens)
        self.assertTrue(tokens.issubset(expanded))


# ---------------------------------------------------------------------------
# LLMClient — retry on transient errors
# ---------------------------------------------------------------------------
class TestLLMClientRetry(unittest.TestCase):
    def _make_client(self):
        """Create an LLMClient instance with all external calls mocked out."""
        with patch("backend.app.utils.llm.ChatBedrockConverse") as mock_cls:
            mock_cls.return_value = MagicMock()
            from backend.app.utils.llm import LLMClient

            client = LLMClient.__new__(LLMClient)
            client._max_tokens = 8000
            client._max_retries = 2
            client._retry_base_delay = 0.0  # no real sleeping in tests
            client.model_id = "test-model"
            client.region = "us-east-1"
            client.full_model_name = "bedrock/test-model"
            client.llm = MagicMock()
        return client

    def test_is_retryable_throttling(self):
        client = self._make_client()
        exc = Exception("ThrottlingException: rate limit exceeded")
        self.assertTrue(client._is_retryable(exc))

    def test_is_retryable_timeout(self):
        client = self._make_client()
        exc = Exception("ModelTimeoutException: model timed out")
        self.assertTrue(client._is_retryable(exc))

    def test_not_retryable_validation_error(self):
        client = self._make_client()
        exc = ValueError("Invalid JSON")
        self.assertFalse(client._is_retryable(exc))

    def test_retries_on_transient_then_succeeds(self):
        client = self._make_client()

        # First call raises throttling, second succeeds
        ok_response = MagicMock()
        ok_response.content = "SELECT 1"
        ok_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

        client.llm.invoke.side_effect = [
            Exception("ThrottlingException: rate exceeded"),
            ok_response,
        ]

        with (
            patch("backend.app.utils.llm.add_tokens"),
            patch("backend.app.utils.llm.logger"),
            patch("backend.app.utils.llm.time.sleep"),
        ):
            result = client.generate("sys", "user")

        self.assertEqual(result, "SELECT 1")
        self.assertEqual(client.llm.invoke.call_count, 2)

    def test_raises_after_max_retries_exhausted(self):
        client = self._make_client()

        client.llm.invoke.side_effect = Exception("ThrottlingException: always fails")

        with (
            patch("backend.app.utils.llm.add_tokens"),
            patch("backend.app.utils.llm.logger"),
            patch("backend.app.utils.llm.time.sleep"),
        ):
            with self.assertRaises(Exception) as ctx:
                client.generate("sys", "user")

        self.assertIn("ThrottlingException", str(ctx.exception))
        # max_retries=2 means 3 total attempts (0,1,2)
        self.assertEqual(client.llm.invoke.call_count, 3)


# ---------------------------------------------------------------------------
# WebKnowledgeService — TTL cache and circuit breaker
# ---------------------------------------------------------------------------
class TestWebKnowledgeServiceCache(unittest.TestCase):
    def setUp(self):
        import backend.app.services.knowledge_service as ks

        ks._KNOWLEDGE_CACHE.clear()
        ks._cb_failures = 0
        ks._cb_opened_at = 0.0

    def test_cache_hit_skips_network(self):
        import backend.app.services.knowledge_service as ks
        from backend.app.services.knowledge_service import WebKnowledgeService

        svc = WebKnowledgeService()
        # Pre-populate cache
        ks._KNOWLEDGE_CACHE["python||"] = ("cached result", time.time() + 300)
        with patch.object(svc, "_search_wikipedia_summary") as mock_wiki:
            result = svc.search_term("python", "")
        mock_wiki.assert_not_called()
        self.assertEqual(result, "cached result")

    def test_circuit_breaker_opens_after_threshold(self):
        import backend.app.services.knowledge_service as ks
        from backend.app.services.knowledge_service import (
            _cb_record_failure,
            _cb_is_open,
        )

        for _ in range(ks._CB_FAILURE_THRESHOLD):
            _cb_record_failure()
        self.assertTrue(_cb_is_open())

    def test_circuit_breaker_resets_after_timeout(self):
        import backend.app.services.knowledge_service as ks
        from backend.app.services.knowledge_service import (
            _cb_record_failure,
            _cb_is_open,
        )

        for _ in range(ks._CB_FAILURE_THRESHOLD):
            _cb_record_failure()
        # Simulate reset window elapsed
        ks._cb_opened_at = time.time() - ks._CB_RESET_AFTER_S - 1
        self.assertFalse(_cb_is_open())


# ---------------------------------------------------------------------------
# PromptQualityGuard — all capability audits
# ---------------------------------------------------------------------------
class TestPromptQualityGuard(unittest.TestCase):
    def _make_profile(self, **flags):
        from backend.app.core.query_analysis.capability_detector import (
            QueryCapabilityProfile,
        )

        return QueryCapabilityProfile(
            requires_joins=flags.get("requires_joins", False),
            requires_aggregation=flags.get("requires_aggregation", False),
            requires_windows=flags.get("requires_windows", False),
            requires_variants=flags.get("requires_variants", False),
            requires_timestamps=flags.get("requires_timestamps", False),
        )

    def _make_nodes(self, content: str = ""):
        from backend.app.core.prompts.prompt_sections import PromptSection

        return [
            PromptSection(
                name="dialect_rules", content=content, priority=1, droppable=True
            )
        ]

    def test_variant_rule_injected_when_missing(self):
        from backend.app.core.quality.prompt_quality_guard import PromptQualityGuard

        nodes = self._make_nodes("")
        profile = self._make_profile(requires_variants=True)
        result = PromptQualityGuard.audit_and_safeguard(nodes, profile, [])
        combined = " ".join(getattr(n, "content", "") for n in result)
        self.assertIn("VARIANT", combined.upper())

    def test_join_rule_injected_when_missing(self):
        from backend.app.core.quality.prompt_quality_guard import PromptQualityGuard

        nodes = self._make_nodes("")
        profile = self._make_profile(requires_joins=True)
        result = PromptQualityGuard.audit_and_safeguard(nodes, profile, [])
        combined = " ".join(getattr(n, "content", "") for n in result)
        self.assertIn("JOIN", combined.upper())

    def test_aggregation_rule_injected_when_missing(self):
        from backend.app.core.quality.prompt_quality_guard import PromptQualityGuard

        nodes = self._make_nodes("")
        profile = self._make_profile(requires_aggregation=True)
        result = PromptQualityGuard.audit_and_safeguard(nodes, profile, [])
        combined = " ".join(getattr(n, "content", "") for n in result)
        self.assertIn("GROUP BY", combined.upper())

    def test_no_injection_when_rules_present(self):
        from backend.app.core.quality.prompt_quality_guard import PromptQualityGuard

        nodes = self._make_nodes("variant join predicate group by date")
        profile = self._make_profile(
            requires_variants=True,
            requires_joins=True,
            requires_aggregation=True,
            requires_timestamps=True,
        )
        original_content = nodes[0].content
        result = PromptQualityGuard.audit_and_safeguard(nodes, profile, [])
        self.assertEqual(result[0].content, original_content)


# ---------------------------------------------------------------------------
# verify_schema_reference — quoted identifier support
# ---------------------------------------------------------------------------
class TestVerifySchemaReferenceQuotedIdentifiers(unittest.TestCase):
    def _make_stabilizer(self, table_name: str, col_names: list):
        from backend.app.utils.stabilizer import ExecutionStabilizer
        from backend.app.models.schemas import (
            SemanticContext,
            SemanticTable,
            SemanticColumn,
        )

        col_objs = [SemanticColumn(name=c, type="TEXT") for c in col_names]
        table = SemanticTable(name=table_name, columns=col_objs)
        ctx = SemanticContext(tables=[table])

        engine = MagicMock()
        engine.context = ctx
        engine.build_context = MagicMock(return_value=ctx)
        engine.discover_and_load_table = MagicMock()

        executor = MagicMock()
        stab = ExecutionStabilizer(executor)
        return stab, engine

    def test_unquoted_valid(self):
        stab, engine = self._make_stabilizer("orders", ["id", "total"])
        ok, msg = stab.verify_schema_reference(
            "SELECT orders.total FROM orders", engine
        )
        self.assertTrue(ok, msg)

    def test_quoted_valid(self):
        stab, engine = self._make_stabilizer("OrderItems", ["UnitPrice"])
        ok, msg = stab.verify_schema_reference(
            'SELECT "OrderItems"."UnitPrice" FROM "OrderItems"', engine
        )
        self.assertTrue(ok, msg)

    def test_invalid_column_detected(self):
        stab, engine = self._make_stabilizer("orders", ["id"])
        ok, msg = stab.verify_schema_reference(
            "SELECT orders.ghost FROM orders", engine
        )
        self.assertFalse(ok)
        self.assertIn("ghost", msg)


if __name__ == "__main__":
    unittest.main()
