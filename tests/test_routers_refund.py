"""
Tests for Refund Router.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routers.refund import router, RefundRequestCreate, RefundRequestResponse
from src.models.refund import RefundStatus


@pytest.fixture
def app():
    """Create a FastAPI app with the refund router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_refund():
    """Create a mock refund object."""
    refund = MagicMock()
    refund.id = "RFR-001"
    refund.order_id = "ORD-001"
    refund.customer_id = "CUST-123"
    refund.amount = 79.99
    refund.reason = "Damaged item"
    refund.status = RefundStatus.PENDING
    refund.external_refund_id = None
    refund.created_at = datetime(2024, 1, 1, 12, 0, 0)
    refund.updated_at = datetime(2024, 1, 1, 12, 0, 0)
    refund.notes = "Refund requested"
    return refund


class TestRefundRequestCreateModel:
    """Tests for RefundRequestCreate model."""

    def test_create_with_all_fields(self):
        """Test creating request with all fields."""
        request = RefundRequestCreate(
            order_id="ORD-001",
            customer_id="CUST-123",
            amount=50.0,
            reason="Damaged item"
        )
        assert request.order_id == "ORD-001"
        assert request.amount == 50.0

    def test_create_without_optional_fields(self):
        """Test creating request without optional fields."""
        request = RefundRequestCreate(
            order_id="ORD-001",
            customer_id="CUST-123"
        )
        assert request.amount is None
        assert request.reason is None


class TestCreateRefundEndpoint:
    """Tests for POST /refunds endpoint."""

    def test_create_refund_success(self, client, mock_refund):
        """Test successful refund creation."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.create_refund_request = AsyncMock(return_value=mock_refund)

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.post("/refunds", json={
                "order_id": "ORD-001",
                "customer_id": "CUST-123",
                "reason": "Damaged item"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "RFR-001"
            assert data["order_id"] == "ORD-001"
            assert data["amount"] == 79.99
            assert data["status"] == "pending"

    def test_create_refund_with_amount(self, client, mock_refund):
        """Test refund creation with custom amount."""
        mock_refund.amount = 50.0
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.create_refund_request = AsyncMock(return_value=mock_refund)

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.post("/refunds", json={
                "order_id": "ORD-001",
                "customer_id": "CUST-123",
                "amount": 50.0
            })

            assert response.status_code == 200
            mock_service.create_refund_request.assert_called_once_with(
                order_id="ORD-001",
                customer_id="CUST-123",
                amount=50.0,
                reason=None
            )

    def test_create_refund_validation_error(self, client):
        """Test refund creation with validation error."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.create_refund_request = AsyncMock(
            side_effect=ValueError("Order not found")
        )

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.post("/refunds", json={
                "order_id": "ORD-NOTFOUND",
                "customer_id": "CUST-123"
            })

            assert response.status_code == 400
            assert "Order not found" in response.json()["detail"]

    def test_create_refund_server_error(self, client):
        """Test refund creation with server error."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.create_refund_request = AsyncMock(
            side_effect=Exception("Database error")
        )

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.post("/refunds", json={
                "order_id": "ORD-001",
                "customer_id": "CUST-123"
            })

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]


class TestGetRefundEndpoint:
    """Tests for GET /refunds/{refund_id} endpoint."""

    def test_get_refund_success(self, client, mock_refund):
        """Test successful refund retrieval."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.get_refund_request = AsyncMock(return_value=mock_refund)

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.get("/refunds/RFR-001")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "RFR-001"
            assert data["order_id"] == "ORD-001"

    def test_get_refund_not_found(self, client):
        """Test refund retrieval when not found."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.get_refund_request = AsyncMock(return_value=None)

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.get("/refunds/RFR-NOTFOUND")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestProcessRefundEndpoint:
    """Tests for POST /refunds/{refund_id}/process endpoint."""

    def test_process_refund_success(self, client):
        """Test successful refund processing."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.process_refund = AsyncMock(return_value={
            "status": "success",
            "refund_id": "RFR-001",
            "external_refund_id": "EXT-001",
            "amount": 79.99,
            "message": "Refund processed successfully"
        })

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.post("/refunds/RFR-001/process")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["refund_id"] == "RFR-001"

    def test_process_refund_validation_error(self, client):
        """Test refund processing with validation error."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.process_refund = AsyncMock(
            side_effect=ValueError("Refund not in pending status")
        )

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.post("/refunds/RFR-001/process")

            assert response.status_code == 400
            assert "not in pending" in response.json()["detail"]

    def test_process_refund_server_error(self, client):
        """Test refund processing with server error."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.process_refund = AsyncMock(
            side_effect=Exception("Payment service unavailable")
        )

        with patch("src.routers.refund.get_db", return_value=mock_db), \
             patch("src.routers.refund.RefundService", return_value=mock_service), \
             patch("src.routers.refund.limiter.limit", lambda x: lambda f: f):

            response = client.post("/refunds/RFR-001/process")

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
