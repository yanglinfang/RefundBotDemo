"""
Health Check Router
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "refund-bot"
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Add checks for database and external service connectivity
    return {
        "status": "ready",
        "service": "refund-bot"
    }
