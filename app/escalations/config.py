"""
Configuration settings for the escalation module using Pydantic v2 and pydantic-settings.
"""
from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EscalationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./escalations.db",
        description="Database connection URL. SQLite default for local/test, PostgreSQL in prod."
    )

    # Auth
    admin_api_key: str = Field(
        default="dev-organizer-secret-key-change-in-production",
        description="API Key/Token required for organizer access to /v1/admin/* endpoints."
    )

    # SMTP Configuration
    smtp_host: str = Field(default="localhost", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_from_email: str = Field(default="no-reply@aws-sbg-kiit.org", description="Sender email address")
    organizer_email: str = Field(default="organizer-alert@aws-sbg-kiit.org", description="Default notification recipient")
    smtp_use_tls: bool = Field(default=True, description="Enable TLS for SMTP connection")

    # Rate Limiting
    rate_limit_per_minute: int = Field(
        default=5,
        description="Maximum POST /v1/escalations requests allowed per client IP per minute."
    )

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="Comma-separated allowed origins for CORS."
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> EscalationSettings:
    """Return cached settings instance."""
    return EscalationSettings()
