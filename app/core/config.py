"""
Core application settings and environment variable validation using Pydantic v2.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    app_env: str = Field(default="development", description="Environment: development, staging, production")
    app_version: str = Field(default="1.0.0", description="Semantic version of application")
    log_level: str = Field(default="INFO", description="Logging level")
    api_prefix: str = Field(default="/v1", description="Prefix for API versioning")
    chat_max_input_chars: int = Field(default=1000, description="Max allowed length of attendee question")
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated CORS origins"
    )

    # Google Gemini LLM Provider (Primary and only LLM)
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-1.5-flash", description="Gemini model identifier")
    llm_timeout_seconds: int = Field(default=15, description="Timeout in seconds for provider calls")
    llm_max_retries: int = Field(default=2, description="Bounded retry attempts for transient errors")

    # Databases & Vector Storage
    database_url: str = Field(
        default="sqlite:///./society_chatbot.db",
        description="SQL database URL (SQLite local, PostgreSQL in prod)"
    )
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant host URL")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant API key if secured remote instance")
    qdrant_collection: str = Field(default="society_events_v1", description="Active Qdrant collection name")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Local Sentence Transformers embedding model"
    )
    redis_url: Optional[str] = Field(default=None, description="Redis URL for shared rate limits across replicas")

    # Auth & Security
    google_client_id: Optional[str] = Field(default=None, description="Google OAuth2 Client ID for ID token validation")
    admin_secret_key: str = Field(
        default="dev-organizer-secret-key-change-in-production",
        description="Service/Admin key for management routes"
    )
    service_api_key: str = Field(
        default="dev-service-api-key-change-in-production",
        description="Backend service-to-service key"
    )

    # Escalation & SMTP Alerts
    smtp_host: str = Field(default="localhost", description="SMTP hostname")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_from_email: str = Field(default="no-reply@aws-sbg-kiit.org", description="Sender email")
    organizer_email: str = Field(default="organizer-alert@aws-sbg-kiit.org", description="Alert recipient")
    smtp_use_tls: bool = Field(default=True, description="Enable TLS for SMTP")

    # Operational Policy Defaults
    anonymous_question_limit: int = Field(
        default=2,
        description="Max questions allowed before Google Sign-In is required"
    )
    max_conversation_followups: int = Field(
        default=6,
        description="Max follow-up questions allowed per conversation"
    )
    per_user_rate_limit_per_minute: int = Field(
        default=10,
        description="Max requests per minute per user/IP"
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
