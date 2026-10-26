"""
Standardized error schemas across all API endpoints.
"""
from typing import Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Standard team-wide API error response envelope.
    Stack traces are never exposed to clients.
    """
    code: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Safe human-readable error description")
    request_id: str = Field(..., description="Unique request tracing ID")
    retry_after_seconds: Optional[int] = Field(
        default=None,
        description="Optional seconds client should wait before retrying"
    )
