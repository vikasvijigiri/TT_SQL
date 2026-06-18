import os
import pytest
from fastapi.testclient import TestClient
from agent.app.api import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint returns 200 and has correct schema."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "overall" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)

def test_results_dates():
    """Test get results dates endpoint returns sorted list of dates."""
    response = client.get("/api/results/dates")
    assert response.status_code == 200
    data = response.json()
    assert "spider" in data
    assert "dab" in data
    assert isinstance(data["spider"], list)
    assert isinstance(data["dab"], list)

def test_spider_metrics():
    """Test Spider metrics endpoint returns core metrics structure."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_processed" in data
    assert "errored_count" in data
    assert "succeeded_count" in data

def test_spider_databases():
    """Test Spider databases list endpoint."""
    response = client.get("/api/databases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        db = data[0]
        assert "name" in db
        assert "results_count" in db
        assert "error_count" in db

def test_spider_recent_results():
    """Test Spider recent results endpoint respects limit query param."""
    response = client.get("/api/results/recent?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5

def test_dab_metrics():
    """Test DAB metrics endpoint returns core accuracy structure."""
    response = client.get("/api/dab/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_queries" in data
    assert "evaluated" in data
    assert "passed" in data
    assert "failed" in data

def test_dab_databases():
    """Test DAB datasets endpoint formatting."""
    response = client.get("/api/dab/databases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_dab_queries():
    """Test DAB queries list endpoint."""
    response = client.get("/api/dab/queries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_dab_status():
    """Test DAB active background tasks endpoint."""
    response = client.get("/api/dab/status")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert isinstance(data["running"], list)

def test_dab_repo_check():
    """Test DAB repository path validation check."""
    response = client.get("/api/dab/repo_check")
    assert response.status_code == 200
    data = response.json()
    assert "repo_path" in data
    assert "exists" in data

def test_improvement_status():
    """Test DAB self-improvement status dashboard statistics."""
    response = client.get("/api/improvement/status")
    assert response.status_code == 200
    data = response.json()
    assert "total_rounds" in data
    assert "rule_counts" in data
    assert "accuracy_trend" in data


def test_demo_query():
    """Test the natural language demo query endpoint against the IPL database."""
    response = client.post("/api/demo/query", json={"query": "Which bowler has the lowest bowling average per wicket taken?"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "sql" in data
    assert "columns" in data
    assert "results" in data


# ---------------------------------------------------------------------------
# Security middleware — API key enforcement
# ---------------------------------------------------------------------------

def test_auth_disabled_by_default_allows_run_all():
    """When ENABLE_AUTH is not set, protected endpoints are reachable without a key."""
    os.environ.pop("ENABLE_AUTH", None)
    os.environ.pop("API_KEY_SECRET", None)
    # Reload module-level vars without restarting the server: patch the globals directly.
    import agent.app.api as api_module
    original_auth = api_module._ENABLE_AUTH
    original_key = api_module._API_KEY_SECRET
    api_module._ENABLE_AUTH = False
    api_module._API_KEY_SECRET = ""
    try:
        # /api/run_all is a POST that starts background work; we expect 200 or 422, not 401.
        response = client.post("/api/run_all?scope=missing_only&workers=1")
        assert response.status_code != 401, "Auth should be disabled — 401 should not be returned"
    finally:
        api_module._ENABLE_AUTH = original_auth
        api_module._API_KEY_SECRET = original_key


def test_auth_enabled_rejects_missing_key():
    """When ENABLE_AUTH=true and API_KEY_SECRET is set, missing key returns 401."""
    import agent.app.api as api_module
    original_auth = api_module._ENABLE_AUTH
    original_key = api_module._API_KEY_SECRET
    api_module._ENABLE_AUTH = True
    api_module._API_KEY_SECRET = "test-secret-key-123"
    try:
        response = client.post("/api/run_all?scope=missing_only&workers=1")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Unauthorized" in data["detail"]
    finally:
        api_module._ENABLE_AUTH = original_auth
        api_module._API_KEY_SECRET = original_key


def test_auth_enabled_accepts_correct_key():
    """When ENABLE_AUTH=true, correct X-API-Key header is accepted (not a 401)."""
    import agent.app.api as api_module
    original_auth = api_module._ENABLE_AUTH
    original_key = api_module._API_KEY_SECRET
    api_module._ENABLE_AUTH = True
    api_module._API_KEY_SECRET = "test-secret-key-123"
    try:
        response = client.post(
            "/api/run_all?scope=missing_only&workers=1",
            headers={"X-API-Key": "test-secret-key-123"},
        )
        assert response.status_code != 401, f"Correct key should not return 401, got {response.status_code}"
    finally:
        api_module._ENABLE_AUTH = original_auth
        api_module._API_KEY_SECRET = original_key


def test_auth_does_not_block_health_endpoint():
    """Health check is never protected — must be reachable even when auth is enabled."""
    import agent.app.api as api_module
    original_auth = api_module._ENABLE_AUTH
    original_key = api_module._API_KEY_SECRET
    api_module._ENABLE_AUTH = True
    api_module._API_KEY_SECRET = "test-secret-key-123"
    try:
        response = client.get("/api/health")
        assert response.status_code == 200
    finally:
        api_module._ENABLE_AUTH = original_auth
        api_module._API_KEY_SECRET = original_key


# ---------------------------------------------------------------------------
# Observability endpoints — latency, prompt integrity, schema drift
# ---------------------------------------------------------------------------

def test_performance_endpoint_returns_schema():
    """/api/performance must return latency + cache keys with correct types."""
    response = client.get("/api/performance")
    assert response.status_code == 200
    data = response.json()
    assert "latency" in data
    assert "cache" in data

    latency = data["latency"]
    assert "sample_count" in latency
    assert "sla" in latency
    assert "targets" in latency["sla"]
    targets = latency["sla"]["targets"]
    assert targets["p50_s"] == 10.0
    assert targets["p95_s"] == 30.0
    assert targets["p99_s"] == 60.0


def test_performance_empty_before_any_query():
    """/api/performance returns null percentiles before any query completes."""
    response = client.get("/api/performance")
    assert response.status_code == 200
    latency = response.json()["latency"]
    # Percentiles may be null if no queries have run in this test session,
    # or populated if another test triggered a query. We only assert types.
    count = latency["sample_count"]
    assert isinstance(count, int)
    if count == 0:
        assert latency["p50_s"] is None
        assert latency["p95_s"] is None
        assert latency["p99_s"] is None


def test_health_includes_prompt_integrity():
    """/api/health must include the prompt_integrity subsystem check."""
    response = client.get("/api/health")
    assert response.status_code == 200
    checks = {c["name"]: c for c in response.json()["checks"]}
    assert "prompt_integrity" in checks
    detail = checks["prompt_integrity"]["detail"]
    assert "prompt_count" in detail
    assert "changed_since_baseline" in detail
    assert "versions" in detail


def test_health_includes_schema_drift():
    """/api/health must include the schema_drift subsystem check."""
    response = client.get("/api/health")
    assert response.status_code == 200
    checks = {c["name"]: c for c in response.json()["checks"]}
    assert "schema_drift" in checks
    detail = checks["schema_drift"]["detail"]
    assert "drifted" in detail
    assert "total_files" in detail


def test_health_includes_latency_sla():
    """/api/health must include the latency_sla subsystem check."""
    response = client.get("/api/health")
    assert response.status_code == 200
    checks = {c["name"]: c for c in response.json()["checks"]}
    assert "latency_sla" in checks
    detail = checks["latency_sla"]["detail"]
    assert "sample_count" in detail
    assert "targets" in detail


# ---------------------------------------------------------------------------
# Group 6 — token monitoring, query analytics, regression gate
# ---------------------------------------------------------------------------

def test_performance_includes_token_stats():
    """/api/performance must include the token_stats section."""
    response = client.get("/api/performance")
    assert response.status_code == 200
    data = response.json()
    assert "tokens" in data
    tokens = data["tokens"]
    assert "total_calls" in tokens
    assert "total_tokens" in tokens
    assert "total_input_tokens" in tokens
    assert "total_output_tokens" in tokens


def test_performance_includes_concurrency():
    """/api/performance must include the concurrency section."""
    response = client.get("/api/performance")
    assert response.status_code == 200
    data = response.json()
    assert "concurrency" in data
    c = data["concurrency"]
    assert "max_concurrent" in c
    assert "inflight" in c
    assert "available_slots" in c


def test_analytics_queries_endpoint_schema():
    """/api/analytics/queries must return events list and limit key."""
    response = client.get("/api/analytics/queries?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert isinstance(data["events"], list)
    assert "limit" in data or "note" in data


def test_analytics_stats_endpoint_schema():
    """/api/analytics/stats must return aggregate stats structure."""
    response = client.get("/api/analytics/stats")
    assert response.status_code == 200
    data = response.json()
    # Either fully populated stats or an initialization note
    assert "total_in_memory" in data or "note" in data


def test_regression_check_endpoint_passes():
    """/api/regression/check must return all_passed=True against IPL database."""
    response = client.get("/api/regression/check")
    assert response.status_code == 200
    data = response.json()
    # If IPL DB is present, all_passed must be True
    if data.get("all_passed") is None:
        # Database not present — skipped gracefully
        assert "note" in data
    else:
        assert data["all_passed"] is True, (
            "Golden regression suite failed:\n"
            + "\n".join(
                f"  {c['name']}: {c.get('error') or c.get('violations')}"
                for c in data.get("cases", [])
                if not c.get("passed")
            )
        )
        assert "cases" in data
        assert isinstance(data["cases"], list)


# ---------------------------------------------------------------------------
# Group 7 — failure analytics, data quality, determinism
# ---------------------------------------------------------------------------

def test_performance_includes_determinism():
    """/api/performance must expose determinism tracking keys."""
    response = client.get("/api/performance")
    assert response.status_code == 200
    data = response.json()
    assert "determinism" in data
    d = data["determinism"]
    assert "total_comparisons" in d
    assert "determinism_score" in d
    assert "matched" in d
    assert "mismatched" in d


def test_performance_includes_data_quality():
    """/api/performance must expose data quality monitoring keys."""
    response = client.get("/api/performance")
    assert response.status_code == 200
    data = response.json()
    assert "data_quality" in data
    q = data["data_quality"]
    assert "sample_count" in q
    assert "avg_quality_score" in q
    assert "alert_threshold" in q


def test_analytics_failures_endpoint_schema():
    """/api/analytics/failures must return events list and failure_groups summary."""
    response = client.get("/api/analytics/failures?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert isinstance(data["events"], list)
    assert "failure_groups" in data or "note" in data


def test_analytics_failures_limit_respected():
    """/api/analytics/failures must accept a limit parameter."""
    response = client.get("/api/analytics/failures?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert len(data["events"]) <= 5


def test_analytics_quality_endpoint_schema():
    """/api/analytics/quality must return rolling quality stats."""
    response = client.get("/api/analytics/quality")
    assert response.status_code == 200
    data = response.json()
    assert "sample_count" in data
    assert "avg_quality_score" in data
    assert "below_threshold_count" in data
    assert "alert_threshold" in data
