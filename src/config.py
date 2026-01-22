"""
Application Configuration

Uses pydantic-settings for environment variable management.
"""

import json
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class LLMEndpoint(BaseModel):
    """
    Configuration for a single LLM endpoint.

    Attributes provide enough metadata for routing strategies to
    weigh cost, latency, and capacity trade-offs.
    """

    name: str
    url: str
    api_key: str = ""
    model: str
    priority: int = 10
    is_local: bool = False
    cost_per_1k_tokens: Optional[float] = None
    request_timeout_seconds: Optional[float] = None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/refund_bot.db"

    # External services
    orders_service_url: str = "http://localhost:8001"
    payments_service_url: str = "http://localhost:8002"

    # LLM Configuration (legacy single-endpoint fields)
    llm_api_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-3.5-turbo"

    # Router configuration
    llm_router_strategy: str = "fallback"
    llm_endpoints_json: str = ""  # JSON string of endpoints
    llm_complexity_threshold: int = 40
    llm_complexity_char_threshold: int = 800
    llm_request_timeout_seconds: float = 20.0

    # Refund Policy
    refund_window_days: int = 30
    max_refund_amount: float = 1000.0

    # Application
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_llm_endpoints(self) -> List[LLMEndpoint]:
        """
        Return configured endpoints, falling back to legacy single-endpoint values.
        """
        if self.llm_endpoints_json and self.llm_endpoints_json.strip():
            try:
                parsed = json.loads(self.llm_endpoints_json)
                return [LLMEndpoint(**ep) for ep in parsed]
            except (json.JSONDecodeError, TypeError):
                pass  # Fall through to default

        return [
            LLMEndpoint(
                name="default",
                url=self.llm_api_url,
                api_key=self.llm_api_key or "dummy-key",
                model=self.llm_model,
                priority=0,
                is_local="localhost" in self.llm_api_url or "ollama" in self.llm_api_url,
            )
        ]


settings = Settings()
