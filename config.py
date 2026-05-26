from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP host settings (repo root import path for webhook / host)."""

    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    GEMINI_API_KEY: str = Field(description="API key for Gemini service authentication.")
    SLACK_CHANNEL_ID: str = Field(description="Reviews channel ID for Slack integration")
    TOOL_REGISTRY_URL: str = Field(description="URL of the tool registry MCP server")

    OPIK_API_KEY: str = Field(default="", description="API key for Opik/Comet integration.")
    OPIK_PROJECT: str = Field(
        default="pr_reviewer_host",
        description="Project name for Comet ML and Opik tracking.",
    )

    @field_validator("GEMINI_API_KEY", "SLACK_CHANNEL_ID", "TOOL_REGISTRY_URL")
    @classmethod
    def check_not_empty(cls, value: str, info) -> str:
        if not value or value.strip() == "":
            logger.error(f"{info.field_name} cannot be empty.")
            raise ValueError(f"{info.field_name} cannot be empty.")
        return value


try:
    settings = Settings()
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise SystemExit(e) from e
