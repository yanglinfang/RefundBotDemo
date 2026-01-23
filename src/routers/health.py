"""
Health Check Router
"""

from fastapi import APIRouter

from src.services.llm_router import get_llm_router
from src.services.debug_stats import get_debug_stats

router = APIRouter()


@router.get("/health")
async def health_check():
    """Base service health check."""
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


@router.get("/health/llm")
async def llm_health(refresh: bool = False):
    """Return health information for all configured LLM endpoints."""
    router_instance = get_llm_router()
    return await router_instance.get_health_report(refresh=refresh)


@router.get("/debug/stats")
async def debug_stats():
    """Return debug statistics for LLM usage."""
    stats_service = get_debug_stats()
    return await stats_service.get_stats()


@router.post("/debug/stats/reset")
async def reset_debug_stats():
    """Reset debug statistics."""
    stats_service = get_debug_stats()
    await stats_service.reset_stats()
    return {"status": "reset"}
