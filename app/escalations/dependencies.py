"""
Authentication dependencies for the Escalation module.
Validates organizer credentials via environment-backed token in ONE isolated place,
allowing effortless replacement when the website's unified auth system is merged.
"""
import uuid
from typing import Optional
from fastapi import Header, HTTPException, status, Request
from app.escalations.config import get_settings


def get_admin_auth(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key"),
) -> str:
    """
    Validates that incoming requests to /v1/admin/* include a valid organizer API key / token.
    Supports both 'Authorization: Bearer <key>' and 'X-Admin-API-Key: <key>'.
    """
    settings = get_settings()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    provided_token: Optional[str] = None

    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_token = parts[1]
        elif len(parts) == 1:
            provided_token = parts[0]
    elif x_admin_api_key:
        provided_token = x_admin_api_key.strip()

    if not provided_token or provided_token != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Invalid or missing organizer authentication token.",
                "request_id": request_id,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token
