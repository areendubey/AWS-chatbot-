"""
Main FastAPI application entrypoint for the Society Chatbot Backend.
Owned by Member 1 (Project Lead).
"""
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.api.errors import register_error_handlers
from app.api.v1.router import v1_router
from app.api.v1.health import router as root_health_router
from app.db.session import init_db

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Starting Society Chatbot API (v%s, env=%s)", settings.app_version, settings.app_env)
    # Initialize database tables
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.warning("Database init failed during startup: %s", str(exc))

    yield

    logger.info("Shutting down Society Chatbot API.")


app = FastAPI(
    title="AWS Cloud Club KIIT - Society Chatbot API",
    description="Production-grade RAG chatbot service for event discovery, queries, and attendee escalations.",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

# 1. Tracing & Latency Middleware
@app.middleware("http")
async def tracing_and_latency_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

    logger.info(
        "Handled %s %s -> status=%d latency=%.2fms [request_id=%s]",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id
    )
    return response


# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Global Exception Handlers
register_error_handlers(app)

# 4. Route Registration
app.include_router(root_health_router)
app.include_router(v1_router)

# Mount Escalation module if present
try:
    from app.escalations.router import router as escalations_router
    app.include_router(escalations_router)
    logger.info("Escalation router mounted successfully.")
except ImportError:
    pass
