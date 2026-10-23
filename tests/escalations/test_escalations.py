"""
Comprehensive test suite for the Escalation module.
Validates all functional requirements, privacy constraints, background email dispatches,
failure survivability, FAQ approval gates, and authentication barriers.
"""
import logging
from app.escalations.models import Escalation


def test_anonymous_escalation_creation(client, db_session, mock_email):
    """
    Ensure anonymous users can successfully submit questions.
    Validates background email dispatch and status transitions.
    """
    payload = {
        "question": "Where is the keynote hall located for the AWS Cloud Day?",
        "wants_followup": False,
        "is_personal": False,
    }
    response = client.post("/v1/escalations", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "reference_id" in data
    assert data["reference_id"].startswith("ESC-")
    assert data["status"] == "open"

    # Verify database state
    escalation = db_session.query(Escalation).filter_by(reference_id=data["reference_id"]).first()
    assert escalation is not None
    assert escalation.wants_followup is False
    assert escalation.contact is None
    assert escalation.email_status == "sent"

    # Verify organizer email alert dispatched
    assert len(mock_email.sent_alerts) == 1
    alert = mock_email.sent_alerts[0]
    assert alert["reference_id"] == data["reference_id"]
    assert alert["wants_followup"] is False
    assert alert["contact"] is None


def test_contact_stored_only_with_followup(client, db_session):
    """
    Privacy Enforcement Test:
    - If wants_followup is False: contact MUST NOT be saved, even if submitted in payload.
    - If wants_followup is True: contact is legitimately preserved for follow-up.
    """
    # Case 1: Attendee sent contact info, but left wants_followup = False
    resp1 = client.post(
        "/v1/escalations",
        json={
            "question": "Can external college participants join the hackathon?",
            "wants_followup": False,
            "contact": "accidental_email@example.com",
        },
    )
    assert resp1.status_code == 201
    esc1 = db_session.query(Escalation).filter_by(reference_id=resp1.json()["reference_id"]).first()
    assert esc1.contact is None, "Contact must be purged when wants_followup is False"

    # Case 2: Attendee explicitly requested follow-up
    resp2 = client.post(
        "/v1/escalations",
        json={
            "question": "Will certificates be provided for the AWS workshop?",
            "wants_followup": True,
            "contact": "attendee@kiit.ac.in",
        },
    )
    assert resp2.status_code == 201
    esc2 = db_session.query(Escalation).filter_by(reference_id=resp2.json()["reference_id"]).first()
    assert esc2.contact == "attendee@kiit.ac.in"


def test_email_failure_still_saves_escalation(client, db_session, mock_email):
    """
    Survivability Test:
    If the email service / SMTP fails, the escalation MUST still be saved.
    The endpoint must never return 500, crash, or lose the submission.
    """
    mock_email.should_fail = True
    mock_email.fail_message = "SMTP Connection Refused: Port 587"

    payload = {
        "question": "Is lunch provided during the all-day AWS workshop?",
        "wants_followup": False,
    }
    response = client.post("/v1/escalations", json=payload)
    assert response.status_code == 201

    ref_id = response.json()["reference_id"]
    escalation = db_session.query(Escalation).filter_by(reference_id=ref_id).first()
    assert escalation is not None
    assert escalation.email_status == "failed"
    assert "SMTP Connection Refused" in escalation.email_error


def test_retry_email_endpoint(client, db_session, mock_email, admin_headers):
    """
    Test organizer can retry sending the alert email for a failed escalation.
    """
    # 1. Simulate failed creation
    mock_email.should_fail = True
    resp = client.post("/v1/escalations", json={"question": "Test retry question."})
    ref_id = resp.json()["reference_id"]

    esc = db_session.query(Escalation).filter_by(reference_id=ref_id).first()
    assert esc.email_status == "failed"

    # 2. Fix email service and retry via admin endpoint
    mock_email.should_fail = False
    retry_resp = client.post(f"/v1/admin/escalations/{ref_id}/retry-email", headers=admin_headers)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["email_status"] == "sent"

    db_session.refresh(esc)
    assert esc.email_status == "sent"
    assert esc.email_error is None


def test_admin_auth_rejection(client):
    """
    Security Test:
    Admin endpoints must reject missing or incorrect authorization credentials.
    Standardized error envelope {code: 'UNAUTHORIZED'} must be returned.
    """
    # 1. Missing header
    resp_no_auth = client.get("/v1/admin/escalations")
    assert resp_no_auth.status_code == 401
    assert resp_no_auth.json()["code"] == "UNAUTHORIZED"

    # 2. Invalid token
    resp_bad_auth = client.get(
        "/v1/admin/escalations",
        headers={"Authorization": "Bearer completely-wrong-token"}
    )
    assert resp_bad_auth.status_code == 401
    assert resp_bad_auth.json()["code"] == "UNAUTHORIZED"


def test_personal_answer_cannot_be_approved_for_faq(client, db_session, admin_headers):
    """
    Privacy Conflict Test:
    Any escalation flagged with is_personal=True MUST be rejected with 409 Conflict.
    """
    resp = client.post(
        "/v1/escalations",
        json={
            "question": "My roll number is 2105123 and my payment got deducted twice.",
            "wants_followup": True,
            "contact": "2105123@kiit.ac.in",
            "is_personal": True,
        },
    )
    ref_id = resp.json()["reference_id"]

    # Attempt to approve for FAQ
    approve_resp = client.post(f"/v1/admin/escalations/{ref_id}/approve-faq", headers=admin_headers)
    assert approve_resp.status_code == 409
    body = approve_resp.json()
    assert body["code"] == "PERSONAL_CONTENT_CONFLICT"

    esc = db_session.query(Escalation).filter_by(reference_id=ref_id).first()
    assert esc.approved_for_faq is False


def test_non_personal_can_be_approved_for_faq(client, db_session, admin_headers):
    """
    Standard general questions can be approved for society FAQ knowledge-base ingestion.
    """
    resp = client.post(
        "/v1/escalations",
        json={
            "question": "What is the Wi-Fi SSID for attendees at Campus 6 auditorium?",
            "wants_followup": False,
            "is_personal": False,
        },
    )
    ref_id = resp.json()["reference_id"]

    approve_resp = client.post(f"/v1/admin/escalations/{ref_id}/approve-faq", headers=admin_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["approved_for_faq"] is True

    esc = db_session.query(Escalation).filter_by(reference_id=ref_id).first()
    assert esc.approved_for_faq is True


def test_answer_triggers_followup_only_when_requested(client, db_session, mock_email, admin_headers):
    """
    Verifies organizer answering workflow:
    - If wants_followup is False: No follow-up email is sent.
    - If wants_followup is True and contact exists: Follow-up email is sent to participant.
    """
    # Scenario A: Anonymous question (no followup)
    resp_a = client.post("/v1/escalations", json={"question": "Where can we park our bikes?"})
    ref_a = resp_a.json()["reference_id"]

    client.post(
        f"/v1/admin/escalations/{ref_a}/answer",
        headers=admin_headers,
        json={"answer": "Parking is available behind Campus 6 block."},
    )
    assert len(mock_email.sent_answers) == 0

    # Scenario B: Participant requested follow-up
    resp_b = client.post(
        "/v1/escalations",
        json={
            "question": "Can I present my project remotely?",
            "wants_followup": True,
            "contact": "participant@kiit.ac.in",
        },
    )
    ref_b = resp_b.json()["reference_id"]

    client.post(
        f"/v1/admin/escalations/{ref_b}/answer",
        headers=admin_headers,
        json={"answer": "Yes, a Google Meet link will be emailed 15 minutes before your slot."},
    )
    assert len(mock_email.sent_answers) == 1
    followup = mock_email.sent_answers[0]
    assert followup["contact"] == "participant@kiit.ac.in"
    assert followup["reference_id"] == ref_b
    assert "Google Meet link" in followup["answer"]


def test_no_contact_details_or_full_question_in_logs(client, caplog):
    """
    Log Privacy Test:
    Never log participant contact details or full question text in application logs.
    """
    secret_contact = "confidential_student_2026@kiit.ac.in"
    secret_question = "SECRET_TOKEN_XYZ_EMERGENCY_ACCESS_QUERY"

    with caplog.at_level(logging.INFO):
        client.post(
            "/v1/escalations",
            json={
                "question": secret_question,
                "wants_followup": True,
                "contact": secret_contact,
            },
        )

    all_logs = " ".join([record.getMessage() for record in caplog.records])
    assert secret_contact not in all_logs, "Participant contact leaked into application logs!"
    assert secret_question not in all_logs, "Full question text leaked into application logs!"


def test_rate_limiting_exceeded(client):
    """
    Abuse Protection Test:
    After exceeding the per-minute limit for POST /v1/escalations from the same IP,
    the API returns HTTP 429 with retry_after_seconds.
    """
    # Settings default is 5 requests per minute
    for _ in range(5):
        resp = client.post("/v1/escalations", json={"question": "Valid rate limit query."})
        assert resp.status_code == 201

    # 6th request must be rejected
    rejected = client.post("/v1/escalations", json={"question": "Exceeded request."})
    assert rejected.status_code == 429
    assert rejected.headers.get("Retry-After") is not None
    data = rejected.json()
    assert data["code"] == "RATE_LIMIT_EXCEEDED"
    assert data["retry_after_seconds"] is not None
