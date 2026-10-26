"""
SQLAlchemy 2.x models for the Escalation module.
Compatible with SQLite and PostgreSQL.
Designed to be easily merged into the team's shared `app/db/models.py`.
"""
import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.escalations.database import Base


def generate_reference_id(prefix: str = "ESC", length: int = 6) -> str:
    """
    Generate a cryptographically secure, human-friendly reference ID using the secrets module.
    Omits ambiguous characters like 0, O, 1, I to avoid misreading.
    Example: ESC-7K3F9Q
    """
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    random_chars = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}-{random_chars}"


class EscalationStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"


class EmailDeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Escalation(Base):
    """
    Represents an escalated user question requiring human organizer attention.
    """
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        default=generate_reference_id,
        doc="Short human-friendly unique ID, e.g. ESC-7K3F9Q"
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
    
    # Privacy fields
    wants_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contact: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Stored ONLY if wants_followup is true. Otherwise must be null."
    )
    is_personal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="True if the question or answer contains personal/sensitive user information."
    )
    approved_for_faq: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Flagged for inclusion in society FAQ. Must remain False if is_personal is True."
    )

    __table_args__ = (
        Index("ix_escalations_status_email", "status", "email_status"),
    )

    def __repr__(self) -> str:
        # Never include question or contact in repr to preserve privacy in debug logs
        return (
            f"<Escalation reference_id={self.reference_id} "
            f"status={self.status} email_status={self.email_status}>"
        )
