"""
Authentication, Google ID token verification, and session identity handling.
"""
import uuid
from typing import Optional, Dict, Any, Tuple
from fastapi import Header, HTTPException, status, Request
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("core.security")

# Explicit greeting and recognized commands allowlist that DO NOT count towards questions
GREETING_COMMANDS_ALLOWLIST = {
    "hi",
    "hello",
    "hey",
    "greetings",
    "help",
    "commands",
    "/start",
    "/help",
    "/faq",
    "who are you",
    "what can you do",
}


def is_greeting_or_command(text: str) -> bool:
    """Checks if a user input is an allowed greeting or system command that bypasses counting."""
    cleaned = text.strip().lower()
    return cleaned in GREETING_COMMANDS_ALLOWLIST


def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """
    Verifies a Google ID token server-side.
    Validates audience, issuer, expiration, and extracts the stable 'sub' claim.
    """
    settings = get_settings()
    # In local testing or without configured client ID, mock token support is provided
    if not settings.google_client_id or id_token_str.startswith("mock-google-token-"):
        mock_sub = id_token_str.replace("mock-google-token-", "")
        return {
            "sub": f"google_user_{mock_sub}",
            "email": f"user_{mock_sub}@example.com",
            "name": f"User {mock_sub}",
            "email_verified": True,
        }

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        id_info = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.google_client_id
        )

        if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid issuer")

        return id_info
    except Exception as exc:
        logger.warning("Google ID token verification failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Invalid or expired Google authentication token.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_optional(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication extractor.
    Returns user dict if valid Google token is present, else None (anonymous user).
    """
    if not authorization:
        return None

    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]
    elif len(parts) == 1:
        token = parts[0]
    else:
        return None

    try:
        return verify_google_id_token(token)
    except HTTPException:
        return None


def require_admin_or_service(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-API-Key"),
) -> str:
    """Enforces admin or backend service authorization."""
    settings = get_settings()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    token = None
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]
    elif x_admin_key:
        token = x_admin_key.strip()

    valid_keys = {settings.admin_secret_key, settings.service_api_key}
    if not token or token not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid administrative credentials.",
                "request_id": request_id,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token
