"""
Refund Service - Business logic for refund processing
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.customer import CustomerProfile
from src.models.refund import RefundRequest, RefundStatus
from src.services.orders_client import OrdersClient
from src.services.payments_client import PaymentsClient
from src.utils.customer_identity import is_email

logger = logging.getLogger(__name__)


class RefundService:
    """Service for handling refund operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.orders_client = OrdersClient()
        self.payments_client = PaymentsClient()

    async def create_refund_request(
        self,
        order_id: str,
        customer_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> RefundRequest:
        """
        Create a new refund request after validating eligibility.
        """
        resolved_customer_id = await self._resolve_customer_identifier(customer_id)

        # Fetch order details
        order = await self.orders_client.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        # Validate customer owns the order
        if order["customer_id"] != resolved_customer_id:
            raise ValueError("Order does not belong to this customer")

        # Validate order status
        if order["status"] not in ["delivered", "shipped"]:
            raise ValueError(f"Order in {order['status']} status is not eligible for refund")

        # Check refund window
        if order.get("delivered_at"):
            delivered_date = datetime.fromisoformat(order["delivered_at"].replace("Z", "+00:00"))
            if datetime.utcnow().replace(tzinfo=delivered_date.tzinfo) - delivered_date > timedelta(days=settings.refund_window_days):
                raise ValueError(f"Order is outside the {settings.refund_window_days}-day refund window")

        # Determine refund amount
        refund_amount = amount if amount is not None else order["total_amount"]

        if refund_amount > order["total_amount"]:
            raise ValueError("Refund amount cannot exceed order total")

        if refund_amount > settings.max_refund_amount:
            raise ValueError(f"Refund amount exceeds maximum allowed (${settings.max_refund_amount})")

        # Create refund request
        refund = RefundRequest(
            id=f"RFR-{uuid.uuid4().hex[:8].upper()}",
            order_id=order_id,
            customer_id=resolved_customer_id,
            amount=refund_amount,
            reason=reason,
            status=RefundStatus.PENDING,
            notes=f"Refund requested for order {order_id}"
        )

        self.db.add(refund)
        await self.db.commit()
        await self.db.refresh(refund)

        logger.info(f"Created refund request {refund.id} for order {order_id}")

        return refund

    async def get_refund_request(self, refund_id: str) -> Optional[RefundRequest]:
        """Get a refund request by ID."""
        result = await self.db.execute(
            select(RefundRequest).where(RefundRequest.id == refund_id)
        )
        return result.scalar_one_or_none()

    async def process_refund(self, refund_id: str) -> dict:
        """
        Process a pending refund request.

        This method:
        1. Validates the refund request
        2. Gets the payment for the order
        3. Creates the refund via payments service
        4. Updates the refund request status
        """
        refund = await self.get_refund_request(refund_id)
        if not refund:
            raise ValueError(f"Refund request {refund_id} not found")

        if refund.status != RefundStatus.PENDING:
            raise ValueError(f"Refund request is not in pending status (current: {refund.status})")

        # Update status to processing
        refund.status = RefundStatus.PROCESSING
        await self.db.commit()

        try:
            # Get payment for the order
            payment = await self.payments_client.get_payment_by_order(refund.order_id)
            if not payment:
                raise ValueError(f"Payment not found for order {refund.order_id}")

            # Create refund via payments service
            refund_result = await self.payments_client.create_refund(
                payment_id=payment["payment_id"],
                amount=refund.amount,
                reason=refund.reason
            )

            # Update refund request
            refund.status = RefundStatus.COMPLETED
            refund.external_refund_id = refund_result["refund_id"]
            refund.completed_at = datetime.utcnow()
            refund.notes = f"Refund processed successfully. External ID: {refund_result['refund_id']}"

            await self.db.commit()

            logger.info(f"Refund {refund_id} processed successfully")

            return {
                "status": "success",
                "refund_id": refund.id,
                "external_refund_id": refund.external_refund_id,
                "amount": refund.amount,
                "message": "Refund processed successfully"
            }

        except Exception as e:
            logger.error(f"Error processing refund {refund_id}: {e}")

            refund.status = RefundStatus.FAILED
            refund.notes = f"Refund failed: {str(e)}"
            await self.db.commit()

            return {
                "status": "failed",
                "refund_id": refund.id,
                "message": str(e)
            }

    async def check_refund_eligibility(self, order_id: str, customer_id: str) -> dict:
        """
        Check if an order is eligible for refund.

        Returns eligibility status and reason.
        """
        try:
            resolved_customer_id = await self._resolve_customer_identifier(customer_id)
        except ValueError as exc:
            return {"eligible": False, "reason": str(exc)}
        order = await self.orders_client.get_order(order_id)

        if not order:
            return {"eligible": False, "reason": "Order not found"}

        if order["customer_id"] != resolved_customer_id:
            return {"eligible": False, "reason": "Order does not belong to this customer"}

        if order["status"] not in ["delivered", "shipped"]:
            return {"eligible": False, "reason": f"Order in {order['status']} status is not eligible"}

        if order.get("delivered_at"):
            delivered_date = datetime.fromisoformat(order["delivered_at"].replace("Z", "+00:00"))
            days_since_delivery = (datetime.utcnow().replace(tzinfo=delivered_date.tzinfo) - delivered_date).days

            if days_since_delivery > settings.refund_window_days:
                return {
                    "eligible": False,
                    "reason": f"Order delivered {days_since_delivery} days ago, outside {settings.refund_window_days}-day window"
                }

        return {
            "eligible": True,
            "reason": "Order is eligible for refund",
            "order": order
        }

    async def _resolve_customer_identifier(self, customer_identifier: str) -> str:
        """
        Normalize a customer identifier. When an email is provided, look up the
        canonical customer ID stored in the database.
        """
        if not customer_identifier or not customer_identifier.strip():
            raise ValueError("Customer identifier is required")

        identifier = customer_identifier.strip()
        if is_email(identifier):
            customer = await self._lookup_customer_by_email(identifier)
            if not customer:
                raise ValueError(f"No customer found for email {identifier}")
            return customer.id

        return identifier

    async def _lookup_customer_by_email(
        self,
        email: str
    ) -> Optional[CustomerProfile]:
        """Look up a customer profile by email address."""
        normalized_email = email.strip().lower()
        result = await self.db.execute(
            select(CustomerProfile).where(CustomerProfile.email == normalized_email)
        )
        return result.scalar_one_or_none()
