"""
Refund Bot - Main Application Entry Point

FastAPI application that provides an LLM-powered refund processing service.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from src.config import settings
from src.database import init_db
from src.limiter import limiter
from src.routers import refund, health, conversation
from src.services.debug_stats import initialize_debug_stats, cleanup_debug_stats

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Refund Bot service...")
    await init_db()
    logger.info("Database initialized")
    await initialize_debug_stats()
    logger.info("Debug stats initialized")
    yield
    # Shutdown
    logger.info("Shutting down Refund Bot service...")
    # Note: We don't cleanup debug stats on shutdown to preserve them for debugging
    # Use POST /debug/stats/reset to manually clear if needed


app = FastAPI(
    title="Refund Bot",
    description="LLM-powered refund processing service",
    version="0.1.0",
    lifespan=lifespan
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS
raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(refund.router, prefix="/api/v1", tags=["Refunds"])
app.include_router(conversation.router, prefix="/api/v1", tags=["Conversation"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
