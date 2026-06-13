import pytest
from fastapi.testclient import TestClient
from backend.app.api import app

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
