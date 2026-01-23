"""
Customer Profile Model.
"""

from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func

from src.database import Base


class CustomerProfile(Base):
    """Represents a customer record used to resolve identifiers."""

    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CustomerProfile(id={self.id}, email={self.email})>"
