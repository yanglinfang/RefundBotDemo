"""
Mock Payments Service

Provides a simulated payments API for testing the Refund Bot.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import logging
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Payments Service", version="1.0.0")


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class RefundStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Payment(BaseModel):
    payment_id: str
    order_id: str
    amount: float
    currency: str = "USD"
    status: PaymentStatus
    payment_method: str
    created_at: datetime
    updated_at: datetime


class Refund(BaseModel):
    refund_id: str
    payment_id: str
    order_id: str
    amount: float
    currency: str = "USD"
    status: RefundStatus
    reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RefundRequest(BaseModel):
    payment_id: str
    amount: float
    reason: Optional[str] = None


# Mock databases
MOCK_PAYMENTS: dict[str, Payment] = {}
MOCK_REFUNDS: dict[str, Refund] = {}


def _seed_mock_payments():
    """Seed some sample payments for testing."""
    now = datetime.utcnow()

    # Payment for ORD-001
    MOCK_PAYMENTS["PAY-001"] = Payment(
        payment_id="PAY-001",
        order_id="ORD-001",
        amount=79.99,
        status=PaymentStatus.COMPLETED,
        payment_method="credit_card",
        created_at=now,
        updated_at=now
    )

    # Payment for ORD-002
    MOCK_PAYMENTS["PAY-002"] = Payment(
        payment_id="PAY-002",
        order_id="ORD-002",
        amount=56.97,
        status=PaymentStatus.COMPLETED,
        payment_method="credit_card",
        created_at=now,
        updated_at=now
    )

    # Payment for ORD-003
    MOCK_PAYMENTS["PAY-003"] = Payment(
        payment_id="PAY-003",
        order_id="ORD-003",
        amount=49.99,
        status=PaymentStatus.PENDING,
        payment_method="paypal",
        created_at=now,
        updated_at=now
    )

    # Payment for ORD-004
    MOCK_PAYMENTS["PAY-004"] = Payment(
        payment_id="PAY-004",
        order_id="ORD-004",
        amount=129.99,
        status=PaymentStatus.COMPLETED,
        payment_method="credit_card",
        created_at=now,
        updated_at=now
    )


# Seed payments on startup
_seed_mock_payments()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-payments"}


@app.get("/payments/{payment_id}", response_model=Payment)
async def get_payment(payment_id: str):
    """Retrieve a payment by ID."""
    logger.info(f"Fetching payment: {payment_id}")

    if payment_id not in MOCK_PAYMENTS:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")

    return MOCK_PAYMENTS[payment_id]


@app.get("/payments/order/{order_id}", response_model=Payment)
async def get_payment_by_order(order_id: str):
    """Retrieve payment for an order."""
    logger.info(f"Fetching payment for order: {order_id}")

    for payment in MOCK_PAYMENTS.values():
        if payment.order_id == order_id:
            return payment

    raise HTTPException(status_code=404, detail=f"Payment for order {order_id} not found")


@app.post("/refunds", response_model=Refund)
async def create_refund(request: RefundRequest):
    """Create a refund for a payment."""
    logger.info(f"Creating refund for payment: {request.payment_id}")

    if request.payment_id not in MOCK_PAYMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Payment {request.payment_id} not found"
        )

    payment = MOCK_PAYMENTS[request.payment_id]

    if payment.status not in [PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot refund payment in {payment.status} status"
        )

    if request.amount > payment.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Refund amount {request.amount} exceeds payment amount {payment.amount}"
        )

    # Create refund
    now = datetime.utcnow()
    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"

    refund = Refund(
        refund_id=refund_id,
        payment_id=request.payment_id,
        order_id=payment.order_id,
        amount=request.amount,
        status=RefundStatus.COMPLETED,  # Simulate instant completion
        reason=request.reason,
        created_at=now,
        updated_at=now
    )

    MOCK_REFUNDS[refund_id] = refund

    # Update payment status
    if request.amount >= payment.amount:
        payment.status = PaymentStatus.REFUNDED
    else:
        payment.status = PaymentStatus.PARTIALLY_REFUNDED
    payment.updated_at = now

    logger.info(f"Refund {refund_id} created successfully for ${request.amount}")

    return refund


@app.get("/refunds/{refund_id}", response_model=Refund)
async def get_refund(refund_id: str):
    """Retrieve a refund by ID."""
    logger.info(f"Fetching refund: {refund_id}")

    if refund_id not in MOCK_REFUNDS:
        raise HTTPException(status_code=404, detail=f"Refund {refund_id} not found")

    return MOCK_REFUNDS[refund_id]


@app.get("/refunds/order/{order_id}", response_model=list[Refund])
async def list_refunds_by_order(order_id: str):
    """List all refunds for an order."""
    logger.info(f"Listing refunds for order: {order_id}")

    refunds = [r for r in MOCK_REFUNDS.values() if r.order_id == order_id]
    return refunds


@app.post("/reset")
async def reset_data():
    """Reset mock data to initial state (for testing)."""
    logger.info("Resetting mock payments data")
    MOCK_PAYMENTS.clear()
    MOCK_REFUNDS.clear()
    _seed_mock_payments()
    return {"status": "reset", "payments_count": len(MOCK_PAYMENTS), "refunds_count": len(MOCK_REFUNDS)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
