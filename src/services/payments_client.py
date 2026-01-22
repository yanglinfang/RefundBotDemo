"""
Payments Service Client - HTTP client for the mock payments service
"""

import logging
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class PaymentsClient:
    """Client for interacting with the Payments service."""

    def __init__(self):
        self.base_url = settings.payments_service_url

    async def get_payment(self, payment_id: str) -> Optional[dict]:
        """Fetch a payment by ID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payments/{payment_id}",
                    timeout=10.0
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error fetching payment {payment_id}: {e}")
            raise

    async def get_payment_by_order(self, order_id: str) -> Optional[dict]:
        """Fetch payment for an order."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payments/order/{order_id}",
                    timeout=10.0
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error fetching payment for order {order_id}: {e}")
            raise

    async def create_refund(
        self,
        payment_id: str,
        amount: float,
        reason: Optional[str] = None
    ) -> dict:
        """Create a refund for a payment."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/refunds",
                    json={
                        "payment_id": payment_id,
                        "amount": amount,
                        "reason": reason
                    },
                    timeout=10.0
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error creating refund for payment {payment_id}: {e}")
            raise

    async def get_refund(self, refund_id: str) -> Optional[dict]:
        """Fetch a refund by ID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/refunds/{refund_id}",
                    timeout=10.0
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error fetching refund {refund_id}: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if the payments service is healthy."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=5.0
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False
