"""
Pydantic v2 schemas for structured event management and registration verification.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.db.models import EventStatus, RegistrationStatus


class EventBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=128)
    aliases: Optional[str] = Field(default=None, description="Comma-separated aliases")
    start_at: datetime
    end_at: datetime
    timezone: str = Field(default="Asia/Kolkata")
    venue: str = Field(..., min_length=2, max_length=255)
    registration_url: Optional[str] = None
    registration_deadline: Optional[datetime] = None
    organizer: str = Field(default="AWS Cloud Club KIIT")
    summary: str = Field(..., min_length=10)
    source_url: Optional[str] = None


class EventCreate(EventBase):
    pass


class EventResponse(EventBase):
    id: int
    event_id: str
    status: EventStatus
    version: int
    is_current: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegistrationStatusResponse(BaseModel):
    """User registration status for a specific event."""
    event_id: str
    event_title: str
    status: RegistrationStatus
    registered_at: datetime
    ticket_code: str
    venue: str
    start_at: datetime

    model_config = ConfigDict(from_attributes=True)
