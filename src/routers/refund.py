"""
Refund API Router
"""

from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.refund_service import RefundService
from src.models.refund import RefundStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class RefundRequestCreate(BaseModel):
    """Schema for creating a refund request."""
    order_id: str
    customer_id: str
    amount: Optional[float] = None  # If None, full refund
    reason: Optional[str] = None


class RefundRequestResponse(BaseModel):
    """Schema for refund request response."""
    id: str
    order_id: str
    customer_id: str
    amount: float
    reason: Optional[str]
    status: RefundStatus
    external_refund_id: Optional[str]
    created_at: str
    updated_at: str
    notes: Optional[str]

    class Config:
        from_attributes = True


@router.post("/refunds", response_model=RefundRequestResponse)
async def create_refund(
    request: RefundRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new refund request."""
    logger.info(f"Creating refund request for order: {request.order_id}")

    service = RefundService(db)

    try:
        refund = await service.create_refund_request(
            order_id=request.order_id,
            customer_id=request.customer_id,
            amount=request.amount,
            reason=request.reason
        )
        return RefundRequestResponse(
            id=refund.id,
            order_id=refund.order_id,
            customer_id=refund.customer_id,
            amount=refund.amount,
            reason=refund.reason,
            status=refund.status,
            external_refund_id=refund.external_refund_id,
            created_at=refund.created_at.isoformat(),
            updated_at=refund.updated_at.isoformat(),
            notes=refund.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating refund: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/refunds/{refund_id}", response_model=RefundRequestResponse)
async def get_refund(
    refund_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a refund request by ID."""
    service = RefundService(db)
    refund = await service.get_refund_request(refund_id)

    if not refund:
        raise HTTPException(status_code=404, detail="Refund request not found")

    return RefundRequestResponse(
        id=refund.id,
        order_id=refund.order_id,
        customer_id=refund.customer_id,
        amount=refund.amount,
        reason=refund.reason,
        status=refund.status,
        external_refund_id=refund.external_refund_id,
        created_at=refund.created_at.isoformat(),
        updated_at=refund.updated_at.isoformat(),
        notes=refund.notes
    )


@router.post("/refunds/{refund_id}/process")
async def process_refund(
    refund_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Process a pending refund request."""
    logger.info(f"Processing refund: {refund_id}")

    service = RefundService(db)

    try:
        result = await service.process_refund(refund_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing refund: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
