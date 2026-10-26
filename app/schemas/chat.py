"""
Pydantic v2 schemas for the student chat endpoint: POST /v1/chat.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ChatStatus(str, Enum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


class SourceItem(BaseModel):
    """Grounded evidence source citation."""
    title: str = Field(..., description="Title of the source event or document")
    url: Optional[str] = Field(default=None, description="Approved public source URL")
    event_id: Optional[str] = Field(default=None, description="UUID of the related event")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of when content was last approved")

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    """Incoming student question payload."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The student's question regarding society events, venues, registration, or FAQs"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Opaque client/server conversation session ID"
    )
    locale: Optional[str] = Field(
        default="en-IN",
        max_length=10,
        description="Preferred language/locale (defaults to en-IN)"
    )


class ChatResponse(BaseModel):
    """Outgoing structured response with grounded sources."""
    answer: str = Field(..., description="Evidence-grounded response text")
    sources: List[SourceItem] = Field(
        default_factory=list,
        description="Validated evidence sources cited in the response. Empty for refusals."
    )
    conversation_id: str = Field(..., description="Stable conversation ID")
    request_id: str = Field(..., description="Unique server request tracing ID")
    status: ChatStatus = Field(..., description="Resolution status of the query")

    model_config = ConfigDict(from_attributes=True)
