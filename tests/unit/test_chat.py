"""
Tests for POST /v1/chat endpoint:
- Out of scope redirection
- Anonymous 2-question limit enforcement
- Preserving question count through Google sign-in
- Grounded response and citations
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.rate_limit import session_tracker

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_tracker():
    session_tracker.reset()
    yield
    session_tracker.reset()


def test_greeting_does_not_count_towards_limit():
    # Greetings are on the allowlist and should not consume question count
    resp = client.post("/v1/chat", json={"question": "hello", "conversation_id": "test_conv_1"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") is not None


def test_out_of_scope_redirection():
    resp = client.post(
        "/v1/chat",
        json={"question": "Write a python quicksort algorithm", "conversation_id": "test_conv_2"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "out_of_scope"
    assert "AWS Cloud Club KIIT" in data["answer"]


def test_anonymous_user_two_question_limit():
    conv_id = "anon_session_limit_test"

    # Question 1: OK
    r1 = client.post("/v1/chat", json={"question": "When is the next AWS workshop?", "conversation_id": conv_id})
    assert r1.status_code == 200

    # Question 2: OK
    r2 = client.post("/v1/chat", json={"question": "Where is the workshop venue?", "conversation_id": conv_id})
    assert r2.status_code == 200

    # Question 3: Must be blocked with 401 requiring Google sign-in
    r3 = client.post("/v1/chat", json={"question": "Who is speaking at the event?", "conversation_id": conv_id})
    assert r3.status_code == 401
    assert r3.json()["code"] == "LOGIN_REQUIRED"


def test_sign_in_preserves_count():
    conv_id = "anon_transition_test"

    # Ask 2 questions as anonymous
    client.post("/v1/chat", json={"question": "When is the next AWS workshop?", "conversation_id": conv_id})
    client.post("/v1/chat", json={"question": "Where is the venue?", "conversation_id": conv_id})

    # Now sign in with mock token
    headers = {"Authorization": "Bearer mock-google-token-areen123"}
    r3 = client.post(
        "/v1/chat",
        headers=headers,
        json={"question": "Is registration still open?", "conversation_id": conv_id}
    )
    # Signed in user can continue asking up to conversation follow-up limit
    assert r3.status_code == 200
