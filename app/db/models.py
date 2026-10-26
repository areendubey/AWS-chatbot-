"""
SQLAlchemy 2.x data models for events, event versions, registrations, and attendee escalations.
"""
import uuid
import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    Integer,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class EventStatus(str, Enum):
    DRAFT = "draft"
    APPROVED_UPCOMING = "approved_upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class RegistrationStatus(str, Enum):
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"
    ATTENDED = "attended"


class Event(Base):
    """
    Authoritative structured record for society events.
    Qdrant is NOT authoritative for dates, venues, deadlines, or approval status.
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Comma-separated alternative names/acronyms")
    status: Mapped[str] = mapped_column(
        SQLEnum(EventStatus, native_enum=False, length=32),
        nullable=False,
        default=EventStatus.DRAFT.value,
        index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    venue: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    registration_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    organizer: Mapped[str] = mapped_column(String(128), default="AWS Cloud Club KIIT", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # Freshness & Versioning
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Event event_id={self.event_id} title='{self.title}' status={self.status} is_current={self.is_current}>"


class EventRegistration(Base):
    """
    Authoritative student registration status.
    Kept strictly out of vector databases; queryable ONLY by authorized users with matching sub.
    """
    __tablename__ = "event_registrations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_sub: Mapped[str] = mapped_column(String(128), index=True, nullable=False, doc="Google verified sub identity")
    event_id: Mapped[str] = mapped_column(String(64), ForeignKey("events.event_id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        SQLEnum(RegistrationStatus, native_enum=False, length=32),
        default=RegistrationStatus.CONFIRMED.value,
        nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    ticket_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    event = relationship("Event", back_populates="registrations")

    __table_args__ = (
        Index("ix_user_event_registration", "user_sub", "event_id", unique=True),
    )


def generate_escalation_ref(prefix: str = "ESC", length: int = 6) -> str:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return f"{prefix}-{''.join(secrets.choice(alphabet) for _ in range(length))}"


class EscalationStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"


class EmailDeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Escalation(Base):
    """
    Attendee escalation model.
    Guarantees privacy: logs never include question or contact text.
    """
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        default=generate_escalation_ref
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    status: Mapped[str] = mapped_column(
        SQLEnum(EscalationStatus, native_enum=False, length=32),
        nullable=False,
        default=EscalationStatus.OPEN.value,
        index=True
    )
    email_status: Mapped[str] = mapped_column(
        SQLEnum(EmailDeliveryStatus, native_enum=False, length=32),
        nullable=False,
        default=EmailDeliveryStatus.PENDING.value,
        index=True
    )
    email_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    wants_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_personal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_for_faq: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_escalations_status_email", "status", "email_status"),
    )

    def __repr__(self) -> str:
        return f"<Escalation reference_id={self.reference_id} status={self.status}>"
