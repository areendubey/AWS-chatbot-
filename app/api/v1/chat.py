"""
Student Chat API route: POST /v1/chat.
Enforces question count quotas, Google Sign-in requirements, and delegates to the Orchestrator.
"""
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.config import get_settings
from app.core.security import get_current_user_optional
from app.core.rate_limit import session_tracker
from app.services.orchestrator import orchestrator_service

router = APIRouter(tags=["Chat"])


@router.post(
    "/v1/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit student inquiry to the society chatbot",
)
def chat_endpoint(
    request_http: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user_identity: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    Main student-facing endpoint:
    - Bounded input length validation.
    - Server-side question quota tracking (anonymous users get 2 questions before Google Sign-In is required).
    - Preserves question count upon sign-in.
    - Prevents rate limit abuse.
    - Returns strict evidence-grounded answers citing approved sources.
    """
    settings = get_settings()
    request_id = getattr(request_http.state, "request_id", str(uuid.uuid4()))

    # Resolve client IP
    client_ip = request_http.client.host if request_http.client else "127.0.0.1"
    forwarded = request_http.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    # 1. Per-IP sliding-window anti-abuse rate limit
    session_tracker.check_rate_limit(client_ip, settings.per_user_rate_limit_per_minute)

    # 2. Session and question count quota check
    # Generate stable session tracking ID from header or IP
    session_id = payload.conversation_id or f"anon_session_{client_ip}"
    user_sub = user_identity.get("sub") if user_identity else None

    # This raises 401 LOGIN_REQUIRED if anonymous user has reached limit
    session_tracker.record_and_check_question(
        session_id=session_id,
        question=payload.question,
        user_sub=user_sub,
    )

    # 3. Process via Orchestrator
    response = orchestrator_service.process_chat_message(
        request=payload,
        db=db,
        request_id=request_id,
        user_identity=user_identity,
    )
    return response
