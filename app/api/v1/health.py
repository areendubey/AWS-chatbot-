"""
Health and readiness endpoints for container orchestrators and load balancers.
"""
from fastapi import APIRouter, status, Response
from sqlalchemy import text
from app.db.session import engine
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("api.health")
router = APIRouter(tags=["Health"])


@router.get("/health/live", status_code=status.HTTP_200_OK, summary="Liveness probe")
def health_live():
    """Returns 200 if the process is running. Makes zero external dependency calls."""
    return {"status": "alive"}


@router.get("/health/ready", summary="Readiness probe")
def health_ready(response: Response):
    """
    Checks that critical dependencies (Database) are reachable.
    Returns 503 if critical dependencies are down so traffic is not routed here.
    """
    settings = get_settings()
    is_ready = True
    details = {}

    # Check database connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        details["database"] = "reachable"
    except Exception as exc:
        is_ready = False
        details["database"] = f"unreachable: {str(exc)}"
        logger.error("Readiness check: Database unreachable: %s", str(exc))

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unready", "details": details}

    return {"status": "ready", "version": settings.app_version, "details": details}
