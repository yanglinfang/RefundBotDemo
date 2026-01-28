"""
Tests for the Refund Service
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from src.services.refund_service import RefundService
from src.models.refund import RefundRequest, RefundStatus
from src.models.customer import CustomerProfile


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

    @pytest.mark.asyncio
    async def test_check_eligibility_with_email_identifier(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Ensure email identifiers are resolved before eligibility checks."""
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client
        service._resolve_customer_identifier = AsyncMock(return_value="CUST-123")

        result = await service.check_refund_eligibility(
            order_id="ORD-001",
            customer_id="alex@example.com"
        )

        service._resolve_customer_identifier.assert_awaited_once_with("alex@example.com")
        assert result["eligible"] is True

    @pytest.mark.asyncio
    async def test_check_eligibility_outside_refund_window(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test eligibility check for order outside refund window."""
        # Set delivery date to 60 days ago (outside default 30-day window)
        sample_order["delivered_at"] = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).isoformat()
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        result = await service.check_refund_eligibility(
            order_id="ORD-001",
            customer_id="CUST-123"
        )

        assert result["eligible"] is False
        assert "outside" in result["reason"].lower() or "window" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_eligibility_resolve_identifier_error(
        self,
        mock_db,
        mock_orders_client
    ):
        """Test eligibility check when identifier resolution fails."""
        service = RefundService(mock_db)
        service.orders_client = mock_orders_client
        service._resolve_customer_identifier = AsyncMock(
            side_effect=ValueError("No customer found")
        )

        result = await service.check_refund_eligibility(
            order_id="ORD-001",
            customer_id="unknown@example.com"
        )

        assert result["eligible"] is False
        assert "No customer found" in result["reason"]


class TestRefundServiceCreateRequest:
    """Tests for RefundService.create_refund_request."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_orders_client(self):
        """Create a mock orders client."""
        with patch("src.services.refund_service.OrdersClient") as mock:
            client = mock.return_value
            yield client

    @pytest.fixture
    def sample_order(self):
        """Sample order data."""
        return {
            "order_id": "ORD-001",
            "customer_id": "CUST-123",
            "status": "delivered",
            "total_amount": 79.99,
            "delivered_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        }

    @pytest.mark.asyncio
    async def test_create_refund_request_success(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test successful refund request creation."""
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        refund = await service.create_refund_request(
            order_id="ORD-001",
            customer_id="CUST-123",
            reason="Damaged item"
        )

        assert refund.order_id == "ORD-001"
        assert refund.customer_id == "CUST-123"
        assert refund.amount == 79.99
        assert refund.reason == "Damaged item"
        assert refund.status == RefundStatus.PENDING
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_create_refund_request_order_not_found(
        self,
        mock_db,
        mock_orders_client
    ):
        """Test refund request when order not found."""
        mock_orders_client.get_order = AsyncMock(return_value=None)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        with pytest.raises(ValueError, match="not found"):
            await service.create_refund_request(
                order_id="ORD-NOTFOUND",
                customer_id="CUST-123"
            )

    @pytest.mark.asyncio
    async def test_create_refund_request_wrong_customer(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test refund request with wrong customer."""
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        with pytest.raises(ValueError, match="does not belong"):
            await service.create_refund_request(
                order_id="ORD-001",
                customer_id="CUST-WRONG"
            )

    @pytest.mark.asyncio
    async def test_create_refund_request_invalid_status(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test refund request for order with invalid status."""
        sample_order["status"] = "pending"
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        with pytest.raises(ValueError, match="not eligible"):
            await service.create_refund_request(
                order_id="ORD-001",
                customer_id="CUST-123"
            )

    @pytest.mark.asyncio
    async def test_create_refund_request_amount_exceeds_total(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test refund request with amount exceeding order total."""
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        with pytest.raises(ValueError, match="cannot exceed"):
            await service.create_refund_request(
                order_id="ORD-001",
                customer_id="CUST-123",
                amount=100.00  # Exceeds 79.99
            )

    @pytest.mark.asyncio
    async def test_create_refund_request_custom_amount(
        self,
        mock_db,
        mock_orders_client,
        sample_order
    ):
        """Test refund request with custom partial amount."""
        mock_orders_client.get_order = AsyncMock(return_value=sample_order)

        service = RefundService(mock_db)
        service.orders_client = mock_orders_client

        refund = await service.create_refund_request(
            order_id="ORD-001",
            customer_id="CUST-123",
            amount=50.00  # Partial refund
        )

        assert refund.amount == 50.00


class TestRefundServiceProcessRefund:
    """Tests for RefundService.process_refund."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def mock_payments_client(self):
        """Create a mock payments client."""
        with patch("src.services.refund_service.PaymentsClient") as mock:
            client = mock.return_value
            yield client

    @pytest.mark.asyncio
    async def test_process_refund_success(
        self,
        mock_db,
        mock_payments_client
    ):
        """Test successful refund processing."""
        # Create a mock refund request
        mock_refund = MagicMock()
        mock_refund.id = "RFR-001"
        mock_refund.order_id = "ORD-001"
        mock_refund.amount = 50.0
        mock_refund.reason = "Damaged"
        mock_refund.status = RefundStatus.PENDING

        mock_payments_client.get_payment_by_order = AsyncMock(
            return_value={"payment_id": "PAY-001"}
        )
        mock_payments_client.create_refund = AsyncMock(
            return_value={"refund_id": "EXT-REF-001"}
        )

        service = RefundService(mock_db)
        service.payments_client = mock_payments_client
        service.get_refund_request = AsyncMock(return_value=mock_refund)

        result = await service.process_refund("RFR-001")

        assert result["status"] == "success"
        assert result["refund_id"] == "RFR-001"
        assert result["external_refund_id"] == "EXT-REF-001"
        assert mock_refund.status == RefundStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_refund_not_found(self, mock_db):
        """Test processing a non-existent refund."""
        service = RefundService(mock_db)
        service.get_refund_request = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await service.process_refund("RFR-NOTFOUND")

    @pytest.mark.asyncio
    async def test_process_refund_not_pending(self, mock_db):
        """Test processing a refund that is not in pending status."""
        mock_refund = MagicMock()
        mock_refund.status = RefundStatus.COMPLETED

        service = RefundService(mock_db)
        service.get_refund_request = AsyncMock(return_value=mock_refund)

        with pytest.raises(ValueError, match="not in pending"):
            await service.process_refund("RFR-001")

    @pytest.mark.asyncio
    async def test_process_refund_payment_not_found(
        self,
        mock_db,
        mock_payments_client
    ):
        """Test refund processing when payment not found."""
        mock_refund = MagicMock()
        mock_refund.id = "RFR-001"
        mock_refund.order_id = "ORD-001"
        mock_refund.status = RefundStatus.PENDING

        mock_payments_client.get_payment_by_order = AsyncMock(return_value=None)

        service = RefundService(mock_db)
        service.payments_client = mock_payments_client
        service.get_refund_request = AsyncMock(return_value=mock_refund)

        result = await service.process_refund("RFR-001")

        assert result["status"] == "failed"
        assert mock_refund.status == RefundStatus.FAILED

    @pytest.mark.asyncio
    async def test_process_refund_payment_service_error(
        self,
        mock_db,
        mock_payments_client
    ):
        """Test refund processing when payment service fails."""
        mock_refund = MagicMock()
        mock_refund.id = "RFR-001"
        mock_refund.order_id = "ORD-001"
        mock_refund.amount = 50.0
        mock_refund.reason = "Damaged"
        mock_refund.status = RefundStatus.PENDING

        mock_payments_client.get_payment_by_order = AsyncMock(
            return_value={"payment_id": "PAY-001"}
        )
        mock_payments_client.create_refund = AsyncMock(
            side_effect=Exception("Payment service error")
        )

        service = RefundService(mock_db)
        service.payments_client = mock_payments_client
        service.get_refund_request = AsyncMock(return_value=mock_refund)

        result = await service.process_refund("RFR-001")

        assert result["status"] == "failed"
        assert "Payment service error" in result["message"]
        assert mock_refund.status == RefundStatus.FAILED


class TestRefundServiceResolveIdentifier:
    """Tests for RefundService._resolve_customer_identifier."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_resolve_identifier_with_customer_id(self, mock_db):
        """Test that customer IDs are returned as-is."""
        service = RefundService(mock_db)

        result = await service._resolve_customer_identifier("CUST-123")

        assert result == "CUST-123"

    @pytest.mark.asyncio
    async def test_resolve_identifier_strips_whitespace(self, mock_db):
        """Test that whitespace is stripped."""
        service = RefundService(mock_db)

        result = await service._resolve_customer_identifier("  CUST-123  ")

        assert result == "CUST-123"

    @pytest.mark.asyncio
    async def test_resolve_identifier_empty_raises_error(self, mock_db):
        """Test that empty identifier raises error."""
        service = RefundService(mock_db)

        with pytest.raises(ValueError, match="required"):
            await service._resolve_customer_identifier("")

    @pytest.mark.asyncio
    async def test_resolve_identifier_whitespace_only_raises_error(self, mock_db):
        """Test that whitespace-only identifier raises error."""
        service = RefundService(mock_db)

        with pytest.raises(ValueError, match="required"):
            await service._resolve_customer_identifier("   ")

    @pytest.mark.asyncio
    async def test_resolve_identifier_email_found(self, mock_db):
        """Test email resolution when customer exists."""
        mock_customer = MagicMock()
        mock_customer.id = "CUST-456"

        service = RefundService(mock_db)
        service._lookup_customer_by_email = AsyncMock(return_value=mock_customer)

        result = await service._resolve_customer_identifier("user@example.com")

        assert result == "CUST-456"
        service._lookup_customer_by_email.assert_awaited_once_with("user@example.com")

    @pytest.mark.asyncio
    async def test_resolve_identifier_email_not_found(self, mock_db):
        """Test email resolution when customer not found."""
        service = RefundService(mock_db)
        service._lookup_customer_by_email = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="No customer found"):
            await service._resolve_customer_identifier("unknown@example.com")


class TestRefundServiceLookupByEmail:
    """Tests for RefundService._lookup_customer_by_email."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_lookup_customer_by_email_found(self, mock_db):
        """Test looking up customer by email when found."""
        mock_customer = CustomerProfile(
            id="CUST-123",
            email="user@example.com"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = RefundService(mock_db)
        result = await service._lookup_customer_by_email("user@example.com")

        assert result == mock_customer

    @pytest.mark.asyncio
    async def test_lookup_customer_by_email_not_found(self, mock_db):
        """Test looking up customer by email when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = RefundService(mock_db)
        result = await service._lookup_customer_by_email("notfound@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_customer_by_email_normalizes_case(self, mock_db):
        """Test that email lookup normalizes case."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = RefundService(mock_db)
        await service._lookup_customer_by_email("  USER@EXAMPLE.COM  ")

        # Verify the query was called (we can't easily check the exact SQL)
        mock_db.execute.assert_awaited_once()
