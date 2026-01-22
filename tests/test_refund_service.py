"""
Tests for the Refund Service
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from src.services.refund_service import RefundService
from src.models.refund import RefundStatus


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    db.add = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_orders_client():
    """Create a mock orders client."""
    with patch("src.services.refund_service.OrdersClient") as mock:
        client = mock.return_value
        yield client


@pytest.fixture
def mock_payments_client():
    """Create a mock payments client."""
    with patch("src.services.refund_service.PaymentsClient") as mock:
        client = mock.return_value
        yield client


@pytest.fixture
def sample_order():
    """Sample order data."""
    now = datetime.utcnow()
    return {
        "order_id": "ORD-001",
        "customer_id": "CUST-123",
        "status": "delivered",
        "total_amount": 79.99,
        "delivered_at": (now - timedelta(days=5)).isoformat()
    }


@pytest.fixture
def sample_payment():
    """Sample payment data."""
    return {
        "payment_id": "PAY-001",
        "order_id": "ORD-001",
        "amount": 79.99,
        "status": "completed"
    }


class TestRefundService:
    """Tests for RefundService."""

    @pytest.mark.asyncio
    async def test_check_eligibility_valid_order(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test eligibility check for a valid order."""
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        result = await service.check_refund_eligibility(
            order_id="ORD-001",
            customer_id="CUST-123"
        )

        assert result["eligible"] is True

    @pytest.mark.asyncio
    async def test_check_eligibility_wrong_customer(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test eligibility check with wrong customer."""
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        result = await service.check_refund_eligibility(
            order_id="ORD-001",
            customer_id="CUST-WRONG"
        )

        assert result["eligible"] is False
        assert "does not belong" in result["reason"]

    @pytest.mark.asyncio
    async def test_check_eligibility_order_not_found(
        self,
        mock_db,
        mock_orders_client
    ):
        """Test eligibility check when order not found."""
        mock_orders_client.get_order = AsyncMock(return_value=None)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        result = await service.check_refund_eligibility(
            order_id="ORD-999",
            customer_id="CUST-123"
        )

        assert result["eligible"] is False
        assert "not found" in result["reason"]

    @pytest.mark.asyncio
    async def test_check_eligibility_pending_order(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test eligibility check for pending order."""
        sample_order["status"] = "pending"
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        result = await service.check_refund_eligibility(
            order_id="ORD-001",
            customer_id="CUST-123"
        )

        assert result["eligible"] is False
        assert "pending" in result["reason"]
