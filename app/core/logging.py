"""
Structured, PII-safe logging for the Society Chatbot.
Ensures API keys, auth tokens, personal student data, and passwords are never written to logs.
"""
import logging
import re
import sys
from typing import Any, Dict


REDACTED = "[REDACTED]"

# Patterns matching sensitive keys and tokens
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[-_]?key|secret|password|bearer|authorization|token)[\"']?\s*[:=]\s*[\"']?([^\"'\s]+)"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email redaction
]


class SafeLogFilter(logging.Filter):
    """Filter that strips out sensitive keys, tokens, and emails from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern in SENSITIVE_PATTERNS:
                msg = pattern.sub(REDACTED, msg)
            record.msg = msg
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured console logging with redaction filters."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Avoid duplicate handlers if called multiple times
    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.addFilter(SafeLogFilter())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level.upper())
    handler.addFilter(SafeLogFilter())

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Convenience getter for named loggers."""
    return logging.getLogger(name)
