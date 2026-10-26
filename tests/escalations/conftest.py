"""
Pytest fixtures for the Escalation module test suite.
Configures isolated in-memory SQLite database, mock email service, and TestClient.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.escalations.database import Base, get_db, SessionLocal
from app.escalations.email_service import get_email_service, MockEmailService, set_email_service
from app.escalations.rate_limiter import limiter
from app.escalations.config import get_settings
from app.escalations.models import Escalation
from scripts.dev_escalations_app import app


@pytest.fixture(scope="session")
def test_engine():
    """In-memory SQLite database shared across test threads via StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal.configure(bind=engine)
    return engine


@pytest.fixture
def db_session(test_engine):
    """Provides a fresh database session and purges records after each test."""
    session = SessionLocal()
    yield session
    session.query(Escalation).delete()
    session.commit()
    session.close()


@pytest.fixture
def mock_email():
    """Mock email service recording dispatches and supporting failure injection."""
    service = MockEmailService()
    set_email_service(service)
    yield service
    set_email_service(None)


@pytest.fixture
def client(db_session, mock_email):
    """FastAPI TestClient with overridden DB session and mock email dependencies."""
    # Reset in-memory rate limiter before each test
    limiter.reset()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_get_email():
        return mock_email

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_service] = override_get_email

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    """Valid organizer authorization headers."""
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.admin_api_key}"}
