"""
Tests for Health Check Router.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routers.health import router


@pytest.fixture
def app():
    """Create a FastAPI app with the health router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_returns_healthy(self, client):
        """Test that health check returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "refund-bot"


class TestReadinessEndpoint:
    """Tests for /ready endpoint."""

    def test_readiness_check_returns_ready(self, client):
        """Test that readiness check returns ready status."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "refund-bot"


class TestLLMHealthEndpoint:
    """Tests for /health/llm endpoint."""

    def test_llm_health_without_refresh(self, client):
        """Test LLM health endpoint without refresh."""
        mock_router = MagicMock()
        mock_router.get_health_report = AsyncMock(return_value={
            "strategy": "fallback",
            "endpoints": {
                "local": {"healthy": True},
                "cloud": {"healthy": True}
            }
        })

        with patch("src.routers.health.get_llm_router", return_value=mock_router):
            response = client.get("/health/llm")

            assert response.status_code == 200
            data = response.json()
            assert data["strategy"] == "fallback"
            assert "endpoints" in data
            mock_router.get_health_report.assert_called_once_with(refresh=False)

    def test_llm_health_with_refresh(self, client):
        """Test LLM health endpoint with refresh=true."""
        mock_router = MagicMock()
        mock_router.get_health_report = AsyncMock(return_value={
            "strategy": "fallback",
            "endpoints": {}
        })

        with patch("src.routers.health.get_llm_router", return_value=mock_router):
            response = client.get("/health/llm?refresh=true")

            assert response.status_code == 200
            mock_router.get_health_report.assert_called_once_with(refresh=True)


class TestDebugStatsEndpoint:
    """Tests for /debug/stats endpoint."""

    def test_debug_stats_returns_stats(self, client):
        """Test that debug stats endpoint returns statistics."""
        mock_stats_service = MagicMock()
        mock_stats_service.get_stats = AsyncMock(return_value={
            "started_at": 1000.0,
            "total_requests": 10,
            "local_requests": 5,
            "cloud_requests": 5,
            "total_tokens": 500,
            "avg_latency_ms": 100.0
        })

        with patch("src.routers.health.get_debug_stats", return_value=mock_stats_service):
            response = client.get("/debug/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_requests"] == 10
            assert data["local_requests"] == 5
            mock_stats_service.get_stats.assert_called_once()


class TestResetDebugStatsEndpoint:
    """Tests for /debug/stats/reset endpoint."""

    def test_reset_debug_stats_returns_success(self, client):
        """Test that reset debug stats endpoint returns success."""
        mock_stats_service = MagicMock()
        mock_stats_service.reset_stats = AsyncMock()

        with patch("src.routers.health.get_debug_stats", return_value=mock_stats_service):
            response = client.post("/debug/stats/reset")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "reset"
            mock_stats_service.reset_stats.assert_called_once()
