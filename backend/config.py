"""
Application configuration using Pydantic BaseSettings.
Loads from environment variables and .env files.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """
    Central configuration for the DevOps Incident Agent.
    All values can be overridden via environment variables or .env file.
    """

    # ── LLM Configuration ──────────────────────────────────────────────
    GEMINI_API_KEY: str = Field(
        ...,
        description="Google Gemini API key for LLM-powered agent reasoning",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model identifier to use across all agents",
    )

    # ── GitHub Integration ─────────────────────────────────────────────
    GITHUB_TOKEN: str = Field(
        default="",
        description="GitHub personal access token for creating issues and PRs",
    )
    GITHUB_REPO: str = Field(
        default="",
        description="Target GitHub repository in 'owner/repo' format",
    )

    # ── Telegram Notifications ─────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Telegram Bot API token for sending incident alerts",
    )
    TELEGRAM_CHAT_ID: str = Field(
        default="",
        description="Telegram chat/channel ID to receive alerts",
    )

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:pass@db:5432/devops_agent",
        description="Async PostgreSQL connection string",
    )

    # ── Monitoring Configuration ───────────────────────────────────────
    LOG_POLL_INTERVAL: int = Field(
        default=30,
        ge=5,
        description="Seconds between background log polling cycles",
    )
    CORRELATION_WINDOW_MINUTES: int = Field(
        default=15,
        ge=1,
        description="Time window (minutes) for correlating related incidents",
    )
    AUTO_RESOLVE_MINUTES: int = Field(
        default=30,
        ge=5,
        description="Minutes of no recurrence before auto-resolving an incident",
    )

    # ── Application ────────────────────────────────────────────────────
    APP_NAME: str = Field(
        default="DevOps Incident Agent",
        description="Application display name",
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Application version",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging",
    )
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.
    Call get_settings() anywhere to access config without re-parsing env.
    """
    return Settings()
