"""
Pydantic v2 schemas for the Escalation module.
Ensures strict validation, consistent error envelopes, and data privacy.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.escalations.models import EscalationStatus, EmailDeliveryStatus


class ErrorResponse(BaseModel):
    """
    Standard team-wide API error response envelope.
    Stack traces are never exposed in production.
    """
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    request_id: str = Field(..., description="Unique request tracing ID")
    retry_after_seconds: Optional[int] = Field(
        default=None,
        description="Optional seconds client should wait before retrying (for rate limits or locks)"
    )


class EscalationCreate(BaseModel):
    """
    Payload for submitting a new user escalation.
    Privacy rules:
    - Questions can be completely anonymous (contact is optional).
    - If wants_followup is False, contact is automatically erased to enforce privacy.
    """
    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The attendee's question or issue requiring organizer assistance."
    )
    wants_followup: bool = Field(
        default=False,
        description="Indicates whether the attendee requests an email response."
    )
    contact: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Email or phone for follow-up. Stored ONLY if wants_followup is True."
    )
    is_personal: bool = Field(
        default=False,
        description="Flag indicating if the inquiry contains personal or private attendee details."
    )

    @model_validator(mode="after")
    def enforce_contact_privacy(self) -> "EscalationCreate":
        # Strict privacy enforcement: never retain contact info unless followup is explicitly requested
        if not self.wants_followup:
            self.contact = None
        elif self.contact:
            self.contact = self.contact.strip()
            if len(self.contact) == 0:
                self.contact = None
        return self


class EscalationPublicResponse(BaseModel):
    """
    Public response returned upon creating an escalation.
    Exposes only the human-friendly reference ID, timestamp, and status.
    """
    reference_id: str
    created_at: datetime
    status: EscalationStatus

    model_config = ConfigDict(from_attributes=True)


class EscalationAdminResponse(BaseModel):
    """
    Full view of an escalation for authenticated organizers.
    """
    id: int
    reference_id: str
    question: str
    created_at: datetime
    status: EscalationStatus
    email_status: EmailDeliveryStatus
    email_error: Optional[str] = None
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None
    wants_followup: bool
    contact: Optional[str] = None
    is_personal: bool
    approved_for_faq: bool

    model_config = ConfigDict(from_attributes=True)


class EscalationListResponse(BaseModel):
    items: List[EscalationAdminResponse]
    total: int


class EscalationAnswerRequest(BaseModel):
    """
    Organizer response payload.
    """
    answer: str = Field(..., min_length=1, max_length=5000, description="Organizer response text.")
    is_personal: Optional[bool] = Field(
        default=None,
        description="Update whether this escalation or answer contains personal info."
    )


class RetryEmailResponse(BaseModel):
    reference_id: str
    email_status: EmailDeliveryStatus
    message: str


class ApproveFaqResponse(BaseModel):
    reference_id: str
    approved_for_faq: bool
    message: str
