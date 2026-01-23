"""
Mock Orders Service

Provides a simulated orders API for testing the Refund Bot.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Orders Service", version="1.0.0")


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float


class Order(BaseModel):
    order_id: str
    customer_id: str
    status: OrderStatus
    items: list[OrderItem]
    total_amount: float
    created_at: datetime
    updated_at: datetime
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


# Mock database of orders
MOCK_ORDERS: dict[str, Order] = {}


def _seed_mock_orders():
    """Seed some sample orders for testing."""
    now = datetime.utcnow()

    # Order 1: Delivered order (eligible for refund)
    MOCK_ORDERS["ORD-001"] = Order(
        order_id="ORD-001",
        customer_id="CUST-123",
        status=OrderStatus.DELIVERED,
        items=[
            OrderItem(
                product_id="PROD-A1",
                product_name="Wireless Headphones",
                quantity=1,
                unit_price=79.99
            )
        ],
        total_amount=79.99,
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(days=3),
        shipped_at=now - timedelta(days=7),
        delivered_at=now - timedelta(days=3)
    )

    # Order 2: Shipped order (may be eligible for refund)
    MOCK_ORDERS["ORD-002"] = Order(
        order_id="ORD-002",
        customer_id="CUST-123",
        status=OrderStatus.SHIPPED,
        items=[
            OrderItem(
                product_id="PROD-B2",
                product_name="USB-C Cable",
                quantity=2,
                unit_price=15.99
            ),
            OrderItem(
                product_id="PROD-C3",
                product_name="Phone Case",
                quantity=1,
                unit_price=24.99
            )
        ],
        total_amount=56.97,
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(days=2),
        shipped_at=now - timedelta(days=2)
    )

    # Order 3: Pending order
    MOCK_ORDERS["ORD-003"] = Order(
        order_id="ORD-003",
        customer_id="CUST-456",
        status=OrderStatus.PENDING,
        items=[
            OrderItem(
                product_id="PROD-D4",
                product_name="Laptop Stand",
                quantity=1,
                unit_price=49.99
            )
        ],
        total_amount=49.99,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2)
    )

    # Order 4: Old delivered order (outside refund window)
    MOCK_ORDERS["ORD-004"] = Order(
        order_id="ORD-004",
        customer_id="CUST-789",
        status=OrderStatus.DELIVERED,
        items=[
            OrderItem(
                product_id="PROD-E5",
                product_name="Keyboard",
                quantity=1,
                unit_price=129.99
            )
        ],
        total_amount=129.99,
        created_at=now - timedelta(days=60),
        updated_at=now - timedelta(days=45),
        shipped_at=now - timedelta(days=55),
        delivered_at=now - timedelta(days=45)
    )


# Seed orders on startup
_seed_mock_orders()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-orders"}


@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    """Retrieve an order by ID."""
    logger.info(f"Fetching order: {order_id}")

    if order_id not in MOCK_ORDERS:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    return MOCK_ORDERS[order_id]


@app.get("/orders", response_model=list[Order])
async def list_orders(customer_id: Optional[str] = None):
    """List all orders, optionally filtered by customer."""
    logger.info(f"Listing orders for customer: {customer_id}")

    orders = list(MOCK_ORDERS.values())

    if customer_id:
        orders = [o for o in orders if o.customer_id == customer_id]

    return orders


@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    """Cancel an order."""
    logger.info(f"Cancelling order: {order_id}")

    if order_id not in MOCK_ORDERS:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    order = MOCK_ORDERS[order_id]

    if order.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order in {order.status} status"
        )

    order.status = OrderStatus.CANCELLED
    order.updated_at = datetime.utcnow()

    return {"message": f"Order {order_id} cancelled successfully"}


@app.post("/reset")
async def reset_data():
    """Reset mock data to initial state (for testing)."""
    logger.info("Resetting mock orders data")
    MOCK_ORDERS.clear()
    _seed_mock_orders()
    return {"status": "reset", "orders_count": len(MOCK_ORDERS)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
