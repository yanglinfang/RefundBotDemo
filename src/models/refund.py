"""
Refund Request Model
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Float, DateTime, Enum, Text
from sqlalchemy.sql import func

from src.database import Base


class RefundStatus(str, PyEnum):
    """Status of a refund request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RefundRequest(Base):
    """Model for tracking refund requests."""

    __tablename__ = "refund_requests"

    id = Column(String, primary_key=True)
    order_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(RefundStatus), default=RefundStatus.PENDING)
    external_refund_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<RefundRequest(id={self.id}, order={self.order_id}, status={self.status})>"
