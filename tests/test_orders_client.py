"""
Tests for Orders Client.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from src.services.orders_client import OrdersClient


class TestOrdersClient:
    """Tests for OrdersClient."""

    @pytest.fixture
    def client(self):
        """Create an OrdersClient instance."""
        with patch("src.services.orders_client.settings") as mock_settings:
            mock_settings.orders_service_url = "http://localhost:8001"
            return OrdersClient()

    @pytest.mark.asyncio
    async def test_get_order_success(self, client):
        """Test successful order retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ORD-001",
            "customer_id": "CUST-123",
            "status": "delivered"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_order("ORD-001")

            assert result["order_id"] == "ORD-001"
            assert result["customer_id"] == "CUST-123"

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, client):
        """Test order retrieval when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_order("ORD-NOTFOUND")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_order_http_error(self, client):
        """Test order retrieval with HTTP error."""
        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(httpx.HTTPError):
                await client.get_order("ORD-001")

    @pytest.mark.asyncio
    async def test_get_user_order_history_success(self, client):
        """Test successful order history retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"order_id": "ORD-001", "status": "delivered"},
            {"order_id": "ORD-002", "status": "shipped"}
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.get_user_order_history()

            assert len(result) == 2
            assert result[0]["order_id"] == "ORD-001"

    @pytest.mark.asyncio
    async def test_get_user_order_history_with_customer_filter(self, client):
        """Test order history retrieval with customer filter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"order_id": "ORD-001", "customer_id": "CUST-123"}
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            result = await client.get_user_order_history(customer_id="CUST-123")

            assert len(result) == 1
            # Verify params were passed
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["params"]["customer_id"] == "CUST-123"

    @pytest.mark.asyncio
    async def test_get_user_order_history_http_error(self, client):
        """Test order history retrieval with HTTP error."""
        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(httpx.HTTPError):
                await client.get_user_order_history()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client):
        """Test health check when service is healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
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

        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, client):
        """Test health check when connection fails."""
        with patch("src.services.orders_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection refused")
            )

            result = await client.health_check()

            assert result is False
