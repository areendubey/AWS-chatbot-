"""
Email service interface and SMTP implementation for organizer alerts and participant follow-up.
Includes mockable abstraction for automated unit and integration tests.
"""
from abc import ABC, abstractmethod
import smtplib
from email.message import EmailMessage
from typing import Optional
import logging

from app.escalations.config import get_settings

logger = logging.getLogger("escalations.email")


class EmailServiceInterface(ABC):
    """
    Abstract interface for all escalation email dispatches.
    Allows easy swapping between live SMTP and mock in-memory service during tests.
    """

    @abstractmethod
    def send_organizer_alert(
        self,
        reference_id: str,
        question: str,
        wants_followup: bool,
        contact: Optional[str] = None
    ) -> None:
        """Alert event organizers of a new attendee escalation."""
        pass

    @abstractmethod
    def send_participant_answer(
        self,
        contact: str,
        reference_id: str,
        question: str,
        answer: str
    ) -> None:
        """Send organizer answer back to the participant."""
        pass


class SMTPEmailService(EmailServiceInterface):
    """
    Standard SMTP implementation using Python's smtplib.
    """

    def __init__(self):
        self.settings = get_settings()

    def send_organizer_alert(
        self,
        reference_id: str,
        question: str,
        wants_followup: bool,
        contact: Optional[str] = None
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"[AWS SBG Alert] New Escalation: {reference_id}"
        msg["From"] = self.settings.smtp_from_email
        msg["To"] = self.settings.organizer_email

        body = (
            f"A new attendee escalation has been submitted.\n\n"
            f"Reference ID: {reference_id}\n"
            f"Follow-up Requested: {'Yes' if wants_followup else 'No (Anonymous)'}\n"
            f"Question:\n{question}\n\n"
            f"Please respond via the organizer dashboard."
        )
        msg.set_content(body)

        self._send(msg)

    def send_participant_answer(
        self,
        contact: str,
        reference_id: str,
        question: str,
        answer: str
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"Update regarding your question [{reference_id}] - AWS SBG KIIT"
        msg["From"] = self.settings.smtp_from_email
        msg["To"] = contact

        body = (
            f"Hello,\n\n"
            f"The AWS SBG KIIT team has answered your question (Ref: {reference_id}):\n\n"
            f"Your Question:\n{question}\n\n"
            f"Organizer Answer:\n{answer}\n\n"
            f"Best regards,\nAWS SBG KIIT Society Team"
        )
        msg.set_content(body)

        self._send(msg)

    def _send(self, msg: EmailMessage) -> None:
        """Perform the low-level SMTP dispatch."""
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as server:
            if self.settings.smtp_use_tls:
                server.starttls()
            if self.settings.smtp_user and self.settings.smtp_password:
                server.login(self.settings.smtp_user, self.settings.smtp_password)
            server.send_message(msg)


class MockEmailService(EmailServiceInterface):
    """
    In-memory mock email service for tests and local dry-runs.
    Records sent messages and can be configured to simulate network/SMTP failures.
    """

    def __init__(self, should_fail: bool = False, fail_message: str = "Simulated SMTP connection timeout"):
        self.sent_alerts = []
        self.sent_answers = []
        self.should_fail = should_fail
        self.fail_message = fail_message

    def send_organizer_alert(
        self,
        reference_id: str,
        question: str,
        wants_followup: bool,
        contact: Optional[str] = None
    ) -> None:
        if self.should_fail:
            raise RuntimeError(self.fail_message)
        self.sent_alerts.append({
            "reference_id": reference_id,
            "question": question,
            "wants_followup": wants_followup,
            "contact": contact,
        })

    def send_participant_answer(
        self,
        contact: str,
        reference_id: str,
        question: str,
        answer: str
    ) -> None:
        if self.should_fail:
            raise RuntimeError(self.fail_message)
        self.sent_answers.append({
            "contact": contact,
            "reference_id": reference_id,
            "question": question,
            "answer": answer,
        })


_global_email_service: Optional[EmailServiceInterface] = None


def get_email_service() -> EmailServiceInterface:
    """
    FastAPI dependency returning the configured email service.
    Defaults to SMTPEmailService, but can be overridden globally or per-test.
    """
    global _global_email_service
    if _global_email_service is None:
        _global_email_service = SMTPEmailService()
    return _global_email_service


def set_email_service(service: Optional[EmailServiceInterface]) -> None:
    """Override the global email service instance (used for testing)."""
    global _global_email_service
    _global_email_service = service
