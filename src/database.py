"""
Database Configuration and Session Management
"""

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=False,
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Initialize database tables and seed reference data."""
    # Import customer models to ensure metadata registration before create_all
    from src.models import customer as _customer_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_initial_data()


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


DEFAULT_CUSTOMERS = [
    {"id": "CUST-123", "email": "alex@example.com", "full_name": "Alex Johnson"},
    {"id": "CUST-456", "email": "sam@example.com", "full_name": "Samantha Lee"},
    {"id": "CUST-789", "email": "mia@example.com", "full_name": "Mia Chen"},
]


async def seed_initial_data():
    """Seed lookup tables required for resolving customer identifiers."""
    from src.models.customer import CustomerProfile

    async with async_session() as session:
        result = await session.execute(
            select(func.count()).select_from(CustomerProfile)
        )
        existing = result.scalar_one()
        if existing:
            return

        session.add_all(
            [
                CustomerProfile(
                    id=record["id"],
                    email=record["email"].lower(),
                    full_name=record["full_name"],
                )
                for record in DEFAULT_CUSTOMERS
            ]
        )
        await session.commit()
        logger.info("Seeded %d customer profiles", len(DEFAULT_CUSTOMERS))
