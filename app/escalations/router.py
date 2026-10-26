"""
FastAPI router for all Escalation endpoints under /v1.
Provides public creation with rate limiting and secure organizer management endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.escalations.database import get_db
from app.escalations.models import EscalationStatus, EmailDeliveryStatus
from app.escalations.schemas import (
    EscalationCreate,
    EscalationPublicResponse,
    EscalationAdminResponse,
    EscalationAnswerRequest,
    RetryEmailResponse,
    ApproveFaqResponse,
)
from app.escalations.dependencies import get_admin_auth
from app.escalations.rate_limiter import rate_limit_dependency
from app.escalations.email_service import EmailServiceInterface, get_email_service
from app.escalations.service import EscalationService

router = APIRouter(tags=["Escalations"])


# ==========================================
# Public Endpoints
# ==========================================

@router.post(
    "/v1/escalations",
    response_model=EscalationPublicResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_dependency)],
    summary="Submit a new attendee question for organizer escalation",
)
def create_escalation(
    payload: EscalationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailServiceInterface = Depends(get_email_service),
):
    """
    Public attendee endpoint:
    - Anonymous questions are fully supported.
    - Rate-limited per client IP to protect against spam and abuse.
    - Contact information is strictly wiped unless wants_followup is explicitly True.
    - Saves record immediately and schedules organizer alert email in a background task.
    - Even if SMTP fails, the escalation is never lost (email_status marked as 'failed').
    """
    escalation = EscalationService.create_escalation(
        payload=payload,
        db=db,
        background_tasks=background_tasks,
        email_service=email_service,
    )
    return escalation


# ==========================================
# Organizer Admin Endpoints
# ==========================================

@router.get(
    "/v1/admin/escalations",
    response_model=List[EscalationAdminResponse],
    summary="List attendee escalations with filtering",
    dependencies=[Depends(get_admin_auth)],
)
def list_escalations(
    status: Optional[EscalationStatus] = None,
    email_status: Optional[EmailDeliveryStatus] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve all attendee escalations.
    Protected by organizer auth token.
    Supports filtering by escalation status and email delivery status.
    """
    status_val = status.value if status else None
    email_val = email_status.value if email_status else None
    return EscalationService.list_escalations(db, status_filter=status_val, email_status_filter=email_val)


@router.post(
    "/v1/admin/escalations/{reference_id}/retry-email",
    response_model=RetryEmailResponse,
    summary="Retry organizer email notification for an escalation",
    dependencies=[Depends(get_admin_auth)],
)
def retry_email(
    reference_id: str,
    db: Session = Depends(get_db),
    email_service: EmailServiceInterface = Depends(get_email_service),
):
    """
    Re-attempts sending the organizer notification email for a previously failed escalation.
    """
    escalation = EscalationService.retry_email(reference_id, db, email_service)
    return RetryEmailResponse(
        reference_id=escalation.reference_id,
        email_status=escalation.email_status,
        message=f"Email notification status is now: {escalation.email_status}",
    )


@router.post(
    "/v1/admin/escalations/{reference_id}/answer",
    response_model=EscalationAdminResponse,
    summary="Answer an attendee escalation and optionally notify attendee",
    dependencies=[Depends(get_admin_auth)],
)
def answer_escalation(
    reference_id: str,
    payload: EscalationAnswerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_service: EmailServiceInterface = Depends(get_email_service),
):
    """
    Record organizer's answer.
    If the attendee requested a follow-up (wants_followup=True) and provided contact info,
    a follow-up email is automatically dispatched via background task.
    """
    return EscalationService.answer_escalation(
        reference_id=reference_id,
        payload=payload,
        db=db,
        background_tasks=background_tasks,
        email_service=email_service,
    )


@router.post(
    "/v1/admin/escalations/{reference_id}/approve-faq",
    response_model=ApproveFaqResponse,
    summary="Approve an escalation question and answer for FAQ ingestion",
    dependencies=[Depends(get_admin_auth)],
)
def approve_faq(
    reference_id: str,
    db: Session = Depends(get_db),
):
    """
    Approves the escalation for inclusion in the society's public knowledge-base / FAQ.
    STRICT PRIVACY RULE: Rejects with 409 Conflict if is_personal is True.
    """
    escalation = EscalationService.approve_for_faq(reference_id, db)
    return ApproveFaqResponse(
        reference_id=escalation.reference_id,
        approved_for_faq=escalation.approved_for_faq,
        message="Escalation successfully approved for public FAQ.",
    )
