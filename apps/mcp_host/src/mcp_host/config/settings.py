from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    OPIK_API_KEY: str | None = Field(default=None, alias="OPIK_API_KEY")
    OPIK_PROJECT: str = Field(default="pr-agent", alias="OPIK_PROJECT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    TOOL_REGISTRY_URL: str = Field(default="http://localhost:8000/mcp", alias="TOOL_REGISTRY_URL")
    SLACK_CHANNEL_ID: str = Field(default="C12345678", alias="SLACK_CHANNEL_ID")
    GEMINI_API_KEY: str = Field(default="", alias="GEMINI_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()  # type: ignore[call-arg]

settings = get_settings()
