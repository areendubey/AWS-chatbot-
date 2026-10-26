"""
Global FastAPI exception handlers to guarantee consistent error envelopes
and ensure internal stack traces are never exposed to clients.
"""
import uuid
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("api.errors")


def register_error_handlers(app: FastAPI) -> None:
    """Registers standard team-wide error handlers on the FastAPI application."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        retry_after = None
        if "Retry-After" in exc.headers if exc.headers else False:
            try:
                retry_after = int(exc.headers["Retry-After"])
            except (ValueError, TypeError):
                pass

        # If detail is already formatted dict
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", "HTTP_ERROR")
            message = exc.detail.get("message", str(exc.detail))
            retry_after = exc.detail.get("retry_after_seconds", retry_after)
        else:
            code = "HTTP_ERROR"
            if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                code = "UNAUTHORIZED"
            elif exc.status_code == status.HTTP_403_FORBIDDEN:
                code = "FORBIDDEN"
            elif exc.status_code == status.HTTP_404_NOT_FOUND:
                code = "NOT_FOUND"
            elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                code = "RATE_LIMIT_EXCEEDED"
            elif exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                code = "SERVICE_UNAVAILABLE"
            message = str(exc.detail)

        headers = dict(exc.headers) if exc.headers else {}
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content={
                "code": code,
                "message": message,
                "request_id": request_id,
                "retry_after_seconds": retry_after,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        error_details = []
        for error in exc.errors():
            loc = " -> ".join(str(item) for item in error.get("loc", []))
            msg = error.get("msg", "Invalid value")
            error_details.append(f"{loc}: {msg}")

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": "VALIDATION_ERROR",
                "message": "; ".join(error_details) if error_details else "Invalid request payload.",
                "request_id": request_id,
                "retry_after_seconds": None,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # Log stack trace internally for developers, never return it to client
        logger.exception("Unhandled server exception occurred for request %s: %s", request_id, str(exc))

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact the administrator with your request ID.",
                "request_id": request_id,
                "retry_after_seconds": None,
            },
        )
