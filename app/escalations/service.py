"""
Business logic and service orchestration for attendee escalations.
Enforces privacy guarantees, safe asynchronous email dispatch, and FAQ approval checks.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.escalations.models import Escalation, EscalationStatus, EmailDeliveryStatus, generate_reference_id
from app.escalations.schemas import EscalationCreate, EscalationAnswerRequest
from app.escalations.email_service import EmailServiceInterface
from app.escalations.database import SessionLocal

logger = logging.getLogger("escalations.service")


def dispatch_organizer_email_task(escalation_id: int, email_service: EmailServiceInterface) -> None:
    """
    Background worker that attempts organizer notification.
    Never blocks the client HTTP response.
    Catches all SMTP errors to ensure the escalation record is NEVER lost or crashed.
    """
    db = SessionLocal()
    try:
        escalation = db.query(Escalation).filter(Escalation.id == escalation_id).first()
        if not escalation:
            logger.error("Background email dispatch failed: Escalation ID %s not found", escalation_id)
            return

        try:
            email_service.send_organizer_alert(
                reference_id=escalation.reference_id,
                question=escalation.question,
                wants_followup=escalation.wants_followup,
                contact=escalation.contact,
            )
            escalation.email_status = EmailDeliveryStatus.SENT.value
            escalation.email_error = None
            db.commit()
            logger.info("Organizer alert sent successfully for escalation: %s", escalation.reference_id)
        except Exception as exc:
            escalation.email_status = EmailDeliveryStatus.FAILED.value
            escalation.email_error = str(exc)
            db.commit()
            logger.warning(
                "Organizer email alert delivery failed for %s. Error recorded: %s",
                escalation.reference_id,
                str(exc)
            )
    finally:
        db.close()


def dispatch_participant_followup_task(escalation_id: int, email_service: EmailServiceInterface) -> None:
    """
    Background worker that sends organizer answer to participant.
    Executes ONLY if wants_followup is true and contact is present.
    """
    db = SessionLocal()
    try:
        escalation = db.query(Escalation).filter(Escalation.id == escalation_id).first()
        if not escalation or not escalation.wants_followup or not escalation.contact or not escalation.answer:
            return

        try:
            email_service.send_participant_answer(
                contact=escalation.contact,
                reference_id=escalation.reference_id,
                question=escalation.question,
                answer=escalation.answer,
            )
            logger.info("Follow-up response email delivered for escalation: %s", escalation.reference_id)
        except Exception as exc:
            logger.error("Participant follow-up delivery failed for %s: %s", escalation.reference_id, str(exc))
    finally:
        db.close()


class EscalationService:
    @staticmethod
    def create_escalation(
        payload: EscalationCreate,
        db: Session,
        background_tasks: BackgroundTasks,
        email_service: EmailServiceInterface,
    ) -> Escalation:
        """
        Create a new escalation with privacy protection.
        Attempts email in background task. If email fails, escalation record is preserved.
        """
        # Privacy guarantee: contact is stored ONLY when wants_followup is True
        sanitized_contact = payload.contact if payload.wants_followup else None

        # Generate unique reference ID with collision safety
        for _ in range(5):
            candidate_id = generate_reference_id()
            existing = db.execute(select(Escalation).where(Escalation.reference_id == candidate_id)).scalar_one_or_none()
            if not existing:
                break
        else:
            candidate_id = generate_reference_id()

        escalation = Escalation(
            reference_id=candidate_id,
            question=payload.question,
            created_at=datetime.now(timezone.utc),
            status=EscalationStatus.OPEN.value,
            email_status=EmailDeliveryStatus.PENDING.value,
            wants_followup=payload.wants_followup,
            contact=sanitized_contact,
            is_personal=payload.is_personal,
            approved_for_faq=False,
        )

        db.add(escalation)
        db.commit()
        db.refresh(escalation)

        # Non-blocking email dispatch in background task
        background_tasks.add_task(dispatch_organizer_email_task, escalation.id, email_service)

        logger.info("Escalation created: %s (wants_followup=%s)", escalation.reference_id, escalation.wants_followup)
        return escalation

    @staticmethod
    def list_escalations(
        db: Session,
        status_filter: Optional[str] = None,
        email_status_filter: Optional[str] = None,
    ) -> List[Escalation]:
        """List escalations with optional status and email_status filters."""
        query = db.query(Escalation)
        if status_filter:
            query = query.filter(Escalation.status == status_filter)
        if email_status_filter:
            query = query.filter(Escalation.email_status == email_status_filter)
        return query.order_by(Escalation.created_at.desc()).all()

    @staticmethod
    def get_by_reference_id(reference_id: str, db: Session) -> Escalation:
        """Fetch escalation by reference ID or raise 404."""
        escalation = db.query(Escalation).filter(Escalation.reference_id == reference_id).first()
        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NOT_FOUND",
                    "message": f"Escalation with reference ID '{reference_id}' not found.",
                },
            )
        return escalation

    @staticmethod
    def retry_email(
        reference_id: str,
        db: Session,
        email_service: EmailServiceInterface,
    ) -> Escalation:
        """
        Retry sending organizer email alert for an existing escalation.
        Updates email_status and email_error accordingly.
        """
        escalation = EscalationService.get_by_reference_id(reference_id, db)
        try:
            email_service.send_organizer_alert(
                reference_id=escalation.reference_id,
                question=escalation.question,
                wants_followup=escalation.wants_followup,
                contact=escalation.contact,
            )
            escalation.email_status = EmailDeliveryStatus.SENT.value
            escalation.email_error = None
            db.commit()
            db.refresh(escalation)
            logger.info("Retry email succeeded for %s", escalation.reference_id)
        except Exception as exc:
            escalation.email_status = EmailDeliveryStatus.FAILED.value
            escalation.email_error = str(exc)
            db.commit()
            db.refresh(escalation)
            logger.warning("Retry email failed for %s: %s", escalation.reference_id, str(exc))

        return escalation

    @staticmethod
    def answer_escalation(
        reference_id: str,
        payload: EscalationAnswerRequest,
        db: Session,
        background_tasks: BackgroundTasks,
        email_service: EmailServiceInterface,
    ) -> Escalation:
        """
        Record organizer answer. If wants_followup is true and contact is stored,
        triggers participant follow-up email.
        """
        escalation = EscalationService.get_by_reference_id(reference_id, db)
        escalation.answer = payload.answer
        escalation.status = EscalationStatus.ANSWERED.value
        escalation.answered_at = datetime.now(timezone.utc)

        if payload.is_personal is not None:
            escalation.is_personal = payload.is_personal
            # If changed to personal, it must not be approved for FAQ
            if escalation.is_personal and escalation.approved_for_faq:
                escalation.approved_for_faq = False

        db.commit()
        db.refresh(escalation)

        # Follow-up email sent ONLY if participant requested it and provided contact info
        if escalation.wants_followup and escalation.contact:
            background_tasks.add_task(dispatch_participant_followup_task, escalation.id, email_service)

        logger.info("Answer recorded for escalation: %s", escalation.reference_id)
        return escalation

    @staticmethod
    def approve_for_faq(reference_id: str, db: Session) -> Escalation:
        """
        Approve escalation question and answer for society FAQ inclusion.
        MUST reject with 409 Conflict if is_personal is True.
        """
        escalation = EscalationService.get_by_reference_id(reference_id, db)

        if escalation.is_personal:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "PERSONAL_CONTENT_CONFLICT",
                    "message": "Cannot approve for FAQ: Escalation is marked as containing personal or sensitive information.",
                },
            )

        escalation.approved_for_faq = True
        db.commit()
        db.refresh(escalation)

        # TODO (Team Integration): Other member responsible for knowledge-base / Qdrant vector store
        # ingestion should hook in here or listen to FAQ approval events.
        logger.info("Escalation %s approved for FAQ", escalation.reference_id)
        return escalation
