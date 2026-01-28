"""
Tests for Payments Client.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from src.services.payments_client import PaymentsClient


class TestPaymentsClient:
    """Tests for PaymentsClient."""

    @pytest.fixture
    def client(self):
        """Create a PaymentsClient instance."""
        with patch("src.services.payments_client.settings") as mock_settings:
            mock_settings.payments_service_url = "http://localhost:8002"
            return PaymentsClient()

    @pytest.mark.asyncio
    async def test_get_payment_success(self, client):
        """Test successful payment retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "payment_id": "PAY-001",
            "order_id": "ORD-001",
            "amount": 79.99,
            "status": "completed"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_payment("PAY-001")

            assert result["payment_id"] == "PAY-001"
            assert result["amount"] == 79.99

    @pytest.mark.asyncio
    async def test_get_payment_not_found(self, client):
        """Test payment retrieval when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_payment("PAY-NOTFOUND")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_payment_http_error(self, client):
        """Test payment retrieval with HTTP error."""
        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(httpx.HTTPError):
                await client.get_payment("PAY-001")

    @pytest.mark.asyncio
    async def test_get_payment_by_order_success(self, client):
        """Test successful payment retrieval by order ID."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "payment_id": "PAY-001",
            "order_id": "ORD-001",
            "amount": 79.99
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_payment_by_order("ORD-001")

            assert result["payment_id"] == "PAY-001"
            assert result["order_id"] == "ORD-001"

    @pytest.mark.asyncio
    async def test_get_payment_by_order_not_found(self, client):
        """Test payment by order retrieval when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_payment_by_order("ORD-NOTFOUND")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_payment_by_order_http_error(self, client):
        """Test payment by order retrieval with HTTP error."""
        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(httpx.HTTPError):
                await client.get_payment_by_order("ORD-001")

    @pytest.mark.asyncio
    async def test_create_refund_success(self, client):
        """Test successful refund creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "refund_id": "REF-001",
            "payment_id": "PAY-001",
            "amount": 50.0,
            "status": "completed"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            result = await client.create_refund(
                payment_id="PAY-001",
                amount=50.0,
                reason="Damaged item"
            )

            assert result["refund_id"] == "REF-001"
            assert result["amount"] == 50.0
            # Verify the request payload
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["payment_id"] == "PAY-001"
            assert call_kwargs["json"]["amount"] == 50.0
            assert call_kwargs["json"]["reason"] == "Damaged item"

    @pytest.mark.asyncio
    async def test_create_refund_without_reason(self, client):
        """Test refund creation without reason."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "refund_id": "REF-001",
            "amount": 50.0
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            result = await client.create_refund(
                payment_id="PAY-001",
                amount=50.0
            )

            assert result["refund_id"] == "REF-001"
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["reason"] is None

    @pytest.mark.asyncio
    async def test_create_refund_http_error(self, client):
        """Test refund creation with HTTP error."""
        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(httpx.HTTPError):
                await client.create_refund("PAY-001", 50.0)

    @pytest.mark.asyncio
    async def test_get_refund_success(self, client):
        """Test successful refund retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "refund_id": "REF-001",
            "amount": 50.0,
            "status": "completed"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_refund("REF-001")

            assert result["refund_id"] == "REF-001"
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_refund_not_found(self, client):
        """Test refund retrieval when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_refund("REF-NOTFOUND")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_refund_http_error(self, client):
        """Test refund retrieval with HTTP error."""
        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(httpx.HTTPError):
                await client.get_refund("REF-001")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client):
        """Test health check when service is healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client):
        """Test health check when service is unhealthy."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, client):
        """Test health check when connection fails."""
        with patch("src.services.payments_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection refused")
            )

            result = await client.health_check()

            assert result is False
