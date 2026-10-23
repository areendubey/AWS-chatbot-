"""
Lightweight development-only runner for the Escalation Module.
Mounts ONLY the escalations router, configures CORS for the dashboard,
and installs privacy-preserving, consistent error JSON handlers.

To run:
    python scripts/dev_escalations_app.py
"""
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.escalations.config import get_settings
from app.escalations.database import Base, engine
from app.escalations.router import router as escalations_router

# Configure privacy-safe console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("dev_escalations_app")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables in local development mode
    Base.metadata.create_all(bind=engine)
    logger.info("Local database tables verified/created.")
    yield


app = FastAPI(
    title="AWS SBG KIIT - Escalation Module (Dev Runner)",
    description="Development runner mounting only the Escalation module router.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware (allows React Vite frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id_and_audit(request: Request, call_next):
    """Assigns unique request_id to each incoming request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ==========================================
# Consistent Error Handlers ({code, message, request_id, retry_after_seconds})
# ==========================================

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "HTTP_ERROR")
        message = exc.detail.get("message", "An error occurred.")
        retry_after = exc.detail.get("retry_after_seconds")
    else:
        code = f"HTTP_{exc.status_code}"
        message = str(exc.detail)
        retry_after = None

    headers = dict(exc.headers or {})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": message,
            "request_id": request_id,
            "retry_after_seconds": retry_after,
        },
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    errors = exc.errors()
    first_msg = errors[0].get("msg", "Invalid request payload.") if errors else "Invalid request data."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": first_msg,
            "request_id": request_id,
            "retry_after_seconds": None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    # Log securely without exposing stack trace to client
    logger.error("Unhandled server exception [req_id=%s]: %s", request_id, type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An internal error occurred. Please contact the organizers.",
            "request_id": request_id,
            "retry_after_seconds": None,
        },
    )


# Mount the escalations router (One line integration for lead)
app.include_router(escalations_router)


if __name__ == "__main__":
    uvicorn.run("scripts.dev_escalations_app:app", host="127.0.0.1", port=8000, reload=True)
