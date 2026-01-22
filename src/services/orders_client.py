"""
Orders Service Client - HTTP client for the mock orders service
"""

import logging
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class OrdersClient:
    """Client for interacting with the Orders service."""

    def __init__(self):
        self.base_url = settings.orders_service_url

    async def get_order(self, order_id: str) -> Optional[dict]:
        """Fetch an order by ID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/orders/{order_id}",
                    timeout=10.0
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error fetching order {order_id}: {e}")
            raise

    async def list_orders(self, customer_id: Optional[str] = None) -> list[dict]:
        """List orders, optionally filtered by customer."""
        try:
            async with httpx.AsyncClient() as client:
                params = {}
                if customer_id:
                    params["customer_id"] = customer_id

                response = await client.get(
                    f"{self.base_url}/orders",
                    params=params,
                    timeout=10.0
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error listing orders: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if the orders service is healthy."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=5.0
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False
