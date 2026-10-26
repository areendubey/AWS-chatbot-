"""
Authoritative event service for structured factual queries (dates, venues, deadlines, links).
SQL database is the authoritative source of truth, not Qdrant.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.db.models import Event, EventStatus, EventRegistration
from app.core.logging import get_logger

logger = get_logger("services.event_service")


class EventService:
    @staticmethod
    def get_upcoming_approved_events(db: Session, limit: int = 10) -> List[Event]:
        """Fetch active, approved upcoming events."""
        stmt = (
            select(Event)
            .where(
                Event.is_current.is_(True),
                Event.status.in_([EventStatus.APPROVED_UPCOMING.value, EventStatus.ONGOING.value])
            )
            .order_by(Event.start_at.asc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def find_event_by_query(db: Session, query_text: str) -> Optional[Event]:
        """Match event by title or alias in user query."""
        clean_text = query_text.lower()
        events = EventService.get_upcoming_approved_events(db, limit=20)
        for ev in events:
            if ev.title.lower() in clean_text or ev.slug.lower() in clean_text:
                return ev
            if ev.aliases:
                aliases = [a.strip().lower() for a in ev.aliases.split(",") if a.strip()]
                if any(alias in clean_text for alias in aliases):
                    return ev
        return None

    @staticmethod
    def get_user_registration(db: Session, user_sub: str, event_id: str) -> Optional[EventRegistration]:
        """
        Fetch registration status for a verified student.
        Strictly requires matched user_sub; never accessible to other attendees.
        """
        stmt = (
            select(EventRegistration)
            .where(
                EventRegistration.user_sub == user_sub,
                EventRegistration.event_id == event_id
            )
        )
        return db.execute(stmt).scalar_one_or_none()
