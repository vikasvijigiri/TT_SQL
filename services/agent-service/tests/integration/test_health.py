"""Integration: backend health endpoint."""
import pytest


def test_health_endpoint():
    try:
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        r = client.get('/health')
        assert r.status_code == 200
        assert r.json()['status'] == 'ok'
    except ImportError:
        pytest.skip('FastAPI/uvicorn not available')
