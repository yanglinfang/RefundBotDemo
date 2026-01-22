"""
Application Configuration

Uses pydantic-settings for environment variable management.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/refund_bot.db"

    # External services
    orders_service_url: str = "http://localhost:8001"
    payments_service_url: str = "http://localhost:8002"

    # LLM Configuration
    llm_api_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-3.5-turbo"

    # Refund Policy
    refund_window_days: int = 30
    max_refund_amount: float = 1000.0

    # Application
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
